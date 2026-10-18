"""Import the upstream CSV contract at an immutable commit, plus public metadata."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote

from .config import REVISION, Source, load_sources, validate_repository
from .io import GitHub, SourceError, read_json, write_json


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def metadata(client: GitHub, repository: str, captured_at: str) -> dict:
    repo = client.json(f"/repos/{repository}")
    if repo.get("private"):
        raise SourceError("this public template supports public repositories only")
    return {
        "repository": repository,
        "github_id": repo["id"],
        "captured_at": captured_at,
        "stars": repo["stargazers_count"],
        "forks": repo["forks_count"],
        "releases": [
            {
                key: release.get(key)
                for key in [
                    "id",
                    "name",
                    "tag_name",
                    "published_at",
                    "html_url",
                    "draft",
                    "prerelease",
                ]
            }
            for release in client.releases(repository)
        ],
    }


def collect_metadata(root: Path, repository: str, destination: Path, client=None) -> dict:
    validate_repository(repository)
    captured_at = now_iso()
    observation = metadata(client or GitHub(), repository, captured_at)
    folder = destination / repository / "metadata"
    name = datetime.fromisoformat(captured_at).strftime("%Y-%m-%d_%H%M%S_%f") + ".json"
    write_json(folder / name, observation)
    return observation


def import_source(
    root: Path,
    source: Source,
    destination: Path,
    *,
    revision=None,
    data_repository=None,
    client=None,
) -> dict:
    client = client or GitHub()
    origin = data_repository or source.data_repository or source.repository
    validate_repository(origin)
    validate_repository(source.repository)
    ref = revision or source.data_branch
    if revision and not REVISION.fullmatch(revision):
        raise ValueError("revision must be a full lowercase Git commit SHA")
    commit = client.json(f"/repos/{origin}/commits/{quote(ref, safe='')}")
    head = commit["sha"]
    # Template-managed branches publish an approved input commit. Legacy branches have no pointer.
    pointer_bytes = client.get(
        f"https://raw.githubusercontent.com/{origin}/{head}/published.json", optional=True
    )
    publication = json.loads(pointer_bytes) if pointer_bytes else None
    sha = publication["data_commit"] if publication and not revision else head
    if not REVISION.fullmatch(sha):
        raise SourceError("invalid published data commit")
    tree = client.json(f"/repos/{origin}/git/trees/{sha}?recursive=1")
    if tree.get("truncated"):
        raise SourceError("GitHub truncated the source tree; refusing a partial import")
    prefix = source.repository + "/"
    files = []
    for entry in tree["tree"]:
        path = entry["path"]
        if entry["type"] != "blob" or not path.startswith(prefix):
            continue
        relative = PurePosixPath(path)
        if ".." in relative.parts:
            raise SourceError("unsafe source path")
        if (path.startswith(prefix + "ghrs-data/") and path.endswith(".csv")) or (
            path.startswith(prefix + "metadata/") and path.endswith(".json")
        ):
            files.append(path)
    required = prefix + "ghrs-data/views_clones_aggregate.csv"
    if required not in files:
        raise SourceError(f"missing {required} in source commit {sha}")
    checksums = {}

    def fetch(path):
        data = client.get(
            f"https://raw.githubusercontent.com/{origin}/{sha}/{quote(path, safe='/')}"
        )
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return path, hashlib.sha256(data).hexdigest()

    with ThreadPoolExecutor(max_workers=6) as pool:
        for path, checksum in pool.map(fetch, files):
            checksums[path] = checksum
    return {
        "repository": source.repository,
        "data_repository": origin,
        "source_revision": sha,
        "source_head": head,
        "publication": publication,
        "files": checksums,
        "expected_refresh_hours": source.expected_refresh_hours,
    }


def sync(
    root: Path,
    *,
    revision=None,
    data_repository=None,
    client=None,
    supplement=True,
    internal_candidate=False,
) -> dict:
    sources = load_sources(root)
    if revision and len(sources) != 1 and not internal_candidate:
        raise ValueError("--revision requires exactly one configured repository")
    directory = root / ".data" / "inputs" / uuid.uuid4().hex
    directory.mkdir(parents=True)
    captured_at = now_iso()
    previous = read_json(root / ".data/sync.json", {})
    try:
        records = []
        for source in sources:
            record = import_source(
                root,
                source,
                directory,
                revision=revision,
                data_repository=data_repository,
                client=client,
            )
            # Retain observations made by previous local syncs; upstream copies take precedence.
            if previous.get("directory"):
                old = root / previous["directory"] / source.repository / "metadata"
                if old.exists():
                    for path in old.glob("*.json"):
                        target = directory / source.repository / "metadata" / path.name
                        if not target.exists():
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(path, target)
            if supplement:
                observation = collect_metadata(root, source.repository, directory, client=client)
                record["github_id"] = observation["github_id"]
            record["files"] = {
                str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (directory / source.repository).rglob("*")
                if p.is_file()
            }
            records.append(record)
        manifest = {
            "version": 1,
            "synced_at": captured_at,
            "directory": str(directory.relative_to(root)),
            "sources": records,
        }
        # Parse every file before activating the candidate. A bad import cannot poison future syncs.
        from .warehouse import parse_inputs

        parse_inputs(root, manifest)
        write_json(directory / "manifest.json", manifest)
        write_json(root / ".data/sync.json", manifest)
        return manifest
    except Exception:
        shutil.rmtree(directory)
        raise


def stage(root: Path, repository: str, destination: Path, *, client=None) -> dict:
    """CI: import an external source if needed, then append one public observation."""
    matching = [s for s in load_sources(root) if s.repository == repository]
    if len(matching) != 1:
        raise ValueError("repository is not configured")
    source = matching[0]
    record = None
    if source.mode == "import":
        record = import_source(root, source, destination, client=client)
        write_json(destination / repository / "upstream.json", record)
    observation = collect_metadata(root, repository, destination, client=client)
    return {"source": record, "observation": observation}


def require_public_sources(root: Path, *, destination=None, client=None) -> None:
    """CI preflight runs before any collector can publish protected traffic."""
    client = client or GitHub()
    repositories = set()
    for source in load_sources(root):
        repositories.add(source.repository)
        if source.mode == "import":
            repositories.add(source.data_repository or source.repository)
    if destination:
        repositories.add(destination)
    for repository in sorted(repositories):
        validate_repository(repository)
        if client.json(f"/repos/{repository}").get("private") is not False:
            raise SourceError(
                "collection/import and the analytics destination require public repositories"
            )

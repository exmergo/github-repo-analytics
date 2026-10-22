"""Import the upstream CSV contract at an immutable commit, plus public metadata."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
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
        # GitHub's subscribers_count is the "Watch" count; watchers_count mirrors stars.
        "watchers": repo.get("subscribers_count"),
        # GitHub counts open pull requests as issues here.
        "open_issues_and_prs": repo.get("open_issues_count"),
        "releases": [
            {
                **{
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
                },
                "assets": [
                    {key: asset.get(key) for key in ["id", "download_count"]}
                    for asset in release.get("assets") or []
                ],
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


def write_csv(path: Path, header: list[str], rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(buffer.getvalue())
    temporary.replace(path)


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))


def day_counts(timestamps: list[str]) -> list[tuple[str, int]]:
    """Aggregate event timestamps to UTC days; identities are never stored."""
    days = Counter(
        datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(timezone.utc).date()
        for t in timestamps
        if t
    )
    return [(day.isoformat(), days[day]) for day in sorted(days)]


ISSUE_FIELDS = ["number", "kind", "created_at", "closed_at", "merged_at", "author_association"]


def collect_issues(client: GitHub, repository: str, folder: Path, state: dict) -> dict:
    """Incremental issue/PR facts merged by number; no logins, titles, or bodies."""
    path = folder / "issues.csv"
    existing = {row["number"]: row for row in read_csv(path)}
    since = (state.get("issues") or {}).get("through")
    route = f"/repos/{repository}/issues?state=all&sort=updated&direction=asc&per_page=100"
    if since and existing:
        # Overlap one hour so items updated during the previous run are not missed.
        overlap = datetime.fromisoformat(since.replace("Z", "+00:00")) - timedelta(hours=1)
        route += "&since=" + overlap.strftime("%Y-%m-%dT%H:%M:%SZ")
    rows, complete = client.paginate(route, max_pages=50)
    through = since
    for item in rows:
        pull = item.get("pull_request")
        existing[str(item["number"])] = {
            "number": str(item["number"]),
            "kind": "pull_request" if pull is not None else "issue",
            "created_at": item["created_at"],
            "closed_at": item.get("closed_at") or "",
            "merged_at": (pull or {}).get("merged_at") or "",
            # GitHub recomputes associations (a merged first-timer becomes CONTRIBUTOR), so the
            # association first observed is kept; backfilled history therefore undercounts.
            "author_association": existing.get(str(item["number"]), {}).get("author_association")
            or item.get("author_association")
            or "NONE",
        }
        through = max(through or "", item["updated_at"])
    write_csv(
        path,
        ISSUE_FIELDS,
        [
            [r[k] for k in ISSUE_FIELDS]
            for r in sorted(existing.values(), key=lambda r: int(r["number"]))
        ],
    )
    return {"complete": complete, "through": through, "items": len(existing)}


def collect_package(client: GitHub, registry: str, package: str, path: Path) -> dict:
    """Daily downloads; registries keep short windows, so history is merged by date."""
    if registry == "pypi":
        body = client.json_url(
            f"https://pypistats.org/api/packages/{package.lower()}/overall?mirrors=false"
        )
        days = {
            r["date"]: int(r["downloads"])
            for r in body["data"]
            if r.get("category") == "without_mirrors"
        }
    else:
        end = datetime.now(timezone.utc).date()
        body = client.json_url(
            f"https://api.npmjs.org/downloads/range/{end - timedelta(days=365)}:{end}/{package}"
        )
        days = {r["day"]: int(r["downloads"]) for r in body["downloads"]}
    merged = {r["date"]: int(r["downloads"]) for r in read_csv(path)}
    # Recent registry days are revised as late logs arrive; the newest response wins.
    merged.update(days)
    write_csv(path, ["date", "downloads"], sorted(merged.items()))
    return {"days": len(merged), "latest": max(merged) if merged else None}


def collect_signals(client: GitHub, source: Source, destination: Path, captured_at: str) -> dict:
    """Public growth and community signals. Stored as aggregates to keep identities out."""
    folder = destination / source.repository / "signals"
    state = read_json(folder / "capture.json", {})
    record = {"captured_at": captured_at, "errors": [], "packages": {}}

    def attempt(name: str, collect, path: Path, previous: dict | None):
        """Each signal degrades alone: keep its last file and capture time, record why."""
        try:
            return {**collect(), "captured_at": captured_at}
        except SourceError as exc:
            record["errors"].append(f"{name}: {exc}")
            if previous and path.exists():
                return {"captured_at": state.get("captured_at"), **previous}
            return None

    def listing(route, accept, field, path, column):
        def collect():
            if accept.endswith("star+json") and getattr(client, "token", "") is None:
                # GitHub answers 401 to anonymous stargazer listings.
                raise SourceError("stargazer dates require a token; set GITHUB_TOKEN")
            rows, complete = client.paginate(route, accept=accept, max_pages=400)
            write_csv(path, ["date", column], day_counts([r[field] for r in rows]))
            return {"complete": complete, "listed": len(rows)}

        return collect

    for name, route, accept, field, column in [
        (
            "stargazers",
            f"/repos/{source.repository}/stargazers?per_page=100",
            "application/vnd.github.star+json",
            "starred_at",
            "stars",
        ),
        (
            "forks",
            f"/repos/{source.repository}/forks?sort=oldest&per_page=100",
            "application/vnd.github+json",
            "created_at",
            "forks",
        ),
    ]:
        path = folder / f"{name}.csv"
        result = attempt(name, listing(route, accept, field, path, column), path, state.get(name))
        if result:
            record[name] = result
    result = attempt(
        "issues",
        lambda: collect_issues(client, source.repository, folder, state),
        folder / "issues.csv",
        state.get("issues"),
    )
    if result:
        record["issues"] = result
    for registry, package in source.package_list():
        key = f"{registry}:{package}"
        path = folder / "downloads" / registry / (package.replace("/", "__") + ".csv")
        # A registry outage keeps prior download history and never blocks GitHub data.
        result = attempt(
            key,
            lambda: collect_package(client, registry, package, path),
            path,
            state.get("packages", {}).get(key),
        )
        if result:
            record["packages"][key] = result
    write_json(folder / "capture.json", record)
    return record


def resolve_tree(client: GitHub, origin: str, sha: str, repository: str) -> tuple[str, list]:
    """List one repository's files without walking the whole, ever-growing data branch."""
    tree = client.json(f"/repos/{origin}/git/trees/{sha}?recursive=1")
    if not tree.get("truncated"):
        return "", tree["tree"]
    # Large multi-project branches: descend owner/repository, then list that subtree only.
    node = sha
    for part in repository.split("/"):
        listing = client.json(f"/repos/{origin}/git/trees/{node}")
        match = [
            e for e in listing["tree"] if e["type"] == "tree" and e["path"].lower() == part.lower()
        ]
        if len(match) != 1:
            raise SourceError(f"missing {repository} in source commit {sha}")
        node = match[0]["sha"]
    subtree = client.json(f"/repos/{origin}/git/trees/{node}?recursive=1")
    if subtree.get("truncated"):
        raise SourceError("GitHub truncated the source tree; refusing a partial import")
    return repository + "/", subtree["tree"]


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


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
    base, entries = resolve_tree(client, origin, sha, source.repository)
    prefix = source.repository.lower() + "/"
    files = {}
    for entry in entries:
        path = base + entry["path"]
        if entry["type"] != "blob" or not path.lower().startswith(prefix):
            continue
        relative = PurePosixPath(path)
        if ".." in relative.parts:
            raise SourceError("unsafe source path")
        # Upstream folder casing may differ from sources.yml; files land under the configured name.
        local = source.repository + path[len(prefix) - 1 :]
        if (
            (local.startswith(source.repository + "/ghrs-data/") and local.endswith(".csv"))
            or (local.startswith(source.repository + "/metadata/") and local.endswith(".json"))
            or (
                local.startswith(source.repository + "/signals/")
                and local.endswith((".csv", ".json"))
            )
        ):
            files[path] = (local, entry.get("sha"))
    required = source.repository + "/ghrs-data/views_clones_aggregate.csv"
    if required not in {local for local, _ in files.values()}:
        raise SourceError(f"missing {required} in source commit {sha}")
    checksums = {}

    cache = root / ".data/blobs"

    def fetch(item):
        path, (local, blob) = item
        cached = cache / blob if blob else None
        if cached and cached.exists():
            data = cached.read_bytes()
        else:
            data = client.get(
                f"https://raw.githubusercontent.com/{origin}/{sha}/{quote(path, safe='/')}"
            )
            if blob:
                if git_blob_sha(data) != blob:
                    raise SourceError(f"downloaded content does not match Git object for {path}")
                cache.mkdir(parents=True, exist_ok=True)
                temporary = cached.with_suffix(".tmp" + uuid.uuid4().hex)
                temporary.write_bytes(data)
                temporary.replace(cached)
        target = destination / local
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return local, hashlib.sha256(data).hexdigest()

    # Content-addressed cache: unchanged history is downloaded once, not on every sync.
    with ThreadPoolExecutor(max_workers=6) as pool:
        for path, checksum in pool.map(fetch, sorted(files.items())):
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


def newer_capture(candidate: Path, current: Path) -> bool:
    """Prefer a local signal history newer than the imported upstream copy."""
    theirs = read_json(candidate / "capture.json", {}).get("captured_at")
    ours = read_json(current / "capture.json", {}).get("captured_at")
    return bool(theirs and (not ours or theirs > ours))


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
    if supplement:
        client = client or GitHub()
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
                old_signals = root / previous["directory"] / source.repository / "signals"
                new_signals = directory / source.repository / "signals"
                if newer_capture(old_signals, new_signals):
                    shutil.rmtree(new_signals, ignore_errors=True)
                    shutil.copytree(old_signals, new_signals)
            if supplement:
                observation = collect_metadata(root, source.repository, directory, client=client)
                record["github_id"] = observation["github_id"]
                record["signals"] = collect_signals(
                    client, source, directory, observation["captured_at"]
                )
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
    matching = [s for s in load_sources(root) if s.repository.lower() == repository.lower()]
    if len(matching) != 1:
        raise ValueError("repository is not configured")
    source = matching[0]
    client = client or GitHub()
    record = None
    if source.mode == "import":
        record = import_source(root, source, destination, client=client)
        write_json(destination / repository / "upstream.json", record)
    observation = collect_metadata(root, repository, destination, client=client)
    signals = collect_signals(client, source, destination, observation["captured_at"])
    return {"source": record, "observation": observation, "signals": signals}


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
        try:
            private = client.json(f"/repos/{repository}").get("private")
        except SourceError as exc:
            # A missing, misspelled, or private repository answers 404: name which one.
            raise SourceError(f"{repository}: {exc}") from None
        if private is not False:
            raise SourceError(
                f"{repository}: collection/import and the analytics destination"
                " require public repositories"
            )

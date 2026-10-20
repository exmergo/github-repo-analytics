"""Strict source parsing and raw-table loading. dbt owns all derived metrics."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb

from .io import read_json

SCHEMAS = {
    "repositories": "repository varchar, repository_identity varchar, source_revision varchar, synced_at timestamptz",
    "traffic": "repository varchar, date date, clones_total bigint, clones_unique bigint, views_total bigint, views_unique bigint",
    "observations": "repository varchar, captured_at timestamptz, stars bigint, forks bigint, watchers bigint, open_issues_and_prs bigint",
    "legacy": "repository varchar, date date, stars bigint, forks bigint",
    "snapshots": "repository varchar, endpoint varchar, captured_at timestamptz, source_file varchar",
    "discovery": "repository varchar, endpoint varchar, captured_at timestamptz, item varchar, views bigint, uniques bigint, reported_rank bigint",
    "releases": "repository varchar, event_id varchar, event_date date, kind varchar, title varchar, url varchar, prerelease boolean",
    "release_assets": "repository varchar, release_id varchar, asset_id varchar, captured_at timestamptz, download_count bigint",
    "signal_captures": "repository varchar, signal varchar, captured_at timestamptz, complete boolean",
    "stargazer_days": "repository varchar, date date, stars bigint",
    "fork_days": "repository varchar, date date, forks bigint",
    "issues": "repository varchar, number bigint, kind varchar, created_at timestamptz, closed_at timestamptz, merged_at timestamptz, author_association varchar",
    "package_downloads": "repository varchar, registry varchar, package varchar, date date, downloads bigint",
}
ASSOCIATIONS = {
    "COLLABORATOR",
    "CONTRIBUTOR",
    "FIRST_TIMER",
    "FIRST_TIME_CONTRIBUTOR",
    "MANNEQUIN",
    "MEMBER",
    "NONE",
    "OWNER",
}
SNAPSHOT = re.compile(r"^(\d{4}-\d{2}-\d{2}_\d{6})_top_(referrers|paths)_snapshot\.csv$")


def timestamp(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"timestamp must include UTC offset: {value}")
    return dt.astimezone(timezone.utc)


def count(value) -> int:
    # Spreadsheet round-trips may write "3.0"; fractional or negative counts stay invalid.
    if isinstance(value, bool) or not re.fullmatch(r"\d+(\.0+)?", str(value)):
        raise ValueError(f"expected a non-negative integer, got {value!r}")
    return int(str(value).split(".")[0])


def optional_count(value):
    return None if value is None else count(value)


def optional_timestamp(value: str):
    return timestamp(value) if value else None


def csv_rows(path: Path, required: list[str], warnings: list[str]) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    fields = reader.fieldnames or []
    if len(set(fields)) != len(fields) or not set(required).issubset(fields):
        raise ValueError(f"{path.name}: missing or duplicate columns; expected {required}")
    extra = set(fields) - set(required)
    if extra:
        warnings.append(f"{path.name}: additional source columns: {sorted(extra)}")
    result = []
    for number, row in enumerate(reader, 2):
        if None in row or any(row.get(k) is None or row[k] == "" for k in required):
            raise ValueError(f"{path.name}:{number}: incomplete or malformed row")
        result.append(row)
    return result


def parse_inputs(root: Path, manifest: dict) -> tuple[dict[str, list], list[str]]:
    base = (root / manifest["directory"]).resolve()
    if not base.is_relative_to(root.resolve() / ".data"):
        raise ValueError("input directory must be inside .data")
    tables = {name: [] for name in SCHEMAS}
    warnings = []
    repositories = set()
    for source in manifest["sources"]:
        repo = source["repository"]
        if repo in repositories:
            raise ValueError("duplicate repository in input manifest")
        repositories.add(repo)
        folder = (base / repo).resolve()
        if not folder.is_relative_to(base):
            raise ValueError("unsafe repository input path")
        for relative, expected_hash in source.get("files", {}).items():
            path = (base / relative).resolve()
            if not path.is_relative_to(folder) or not path.is_file():
                raise ValueError("missing or unsafe input file in manifest")
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
                raise ValueError(
                    "input checksum changed; run sync to obtain a new immutable candidate"
                )
        ghrs = folder / "ghrs-data"
        rows = csv_rows(
            ghrs / "views_clones_aggregate.csv",
            ["time_iso8601", "clones_total", "clones_unique", "views_total", "views_unique"],
            warnings,
        )
        seen = set()
        for r in rows:
            dt = timestamp(r["time_iso8601"])
            if dt.hour or dt.minute or dt.second or dt.microsecond or dt.date() in seen:
                raise ValueError("traffic requires one unique UTC-midnight row per date")
            seen.add(dt.date())
            values = [
                count(r[k])
                for k in ["clones_total", "clones_unique", "views_total", "views_unique"]
            ]
            if values[1] > values[0] or values[3] > values[2]:
                raise ValueError("traffic uniques exceed totals")
            tables["traffic"].append((repo, dt.date(), *values))
        legacy = {}
        for filename, field, index in [
            ("stargazers.csv", "stars_cumulative", 0),
            ("forks.csv", "forks_cumulative", 1),
        ]:
            path = ghrs / filename
            if not path.exists():
                warnings.append(f"{repo}: {filename} unavailable")
                continue
            seen = set()
            for r in csv_rows(path, ["time_iso8601", field], warnings):
                day = timestamp(r["time_iso8601"]).date()
                if day in seen:
                    raise ValueError(f"{filename}: duplicate source date")
                seen.add(day)
                legacy.setdefault(day, [None, None])[index] = count(r[field])
        for day, values in sorted(legacy.items()):
            tables["legacy"].append((repo, day, *values))
        for path in sorted((ghrs / "snapshots").glob("*.csv")):
            match = SNAPSHOT.fullmatch(path.name)
            if not match:
                warnings.append(f"{repo}: ignored unsupported upstream snapshot {path.name}")
                continue
            captured = datetime.strptime(match[1], "%Y-%m-%d_%H%M%S").replace(tzinfo=timezone.utc)
            endpoint = match[2]
            field = "referrer" if endpoint == "referrers" else "url_path"
            rows = csv_rows(path, [field, "views_total", "views_unique"], warnings)
            tables["snapshots"].append((repo, endpoint, captured, path.name))
            seen = set()
            if len(rows) > 10:
                raise ValueError(f"{path.name}: expected at most ten reported items")
            for rank, r in enumerate(rows, 1):
                item = r[field]
                if item in seen:
                    raise ValueError(f"{path.name}: duplicate item")
                seen.add(item)
                views, uniques = count(r["views_total"]), count(r["views_unique"])
                if uniques > views:
                    raise ValueError(f"{path.name}: uniques exceed total views")
                tables["discovery"].append((repo, endpoint, captured, item, views, uniques, rank))
        captures = set()
        releases = {}
        github_id = count(source["github_id"]) if source.get("github_id") is not None else None
        for path in sorted((folder / "metadata").glob("*.json")):
            observation = read_json(path)
            if observation["repository"] != repo:
                raise ValueError("metadata repository mismatch")
            captured = timestamp(observation["captured_at"])
            if captured in captures:
                raise ValueError("duplicate metadata capture timestamp")
            captures.add(captured)
            if github_id is not None and github_id != observation["github_id"]:
                raise ValueError("repository identity changed; review configuration")
            github_id = count(observation["github_id"])
            tables["observations"].append(
                (
                    repo,
                    captured,
                    count(observation["stars"]),
                    count(observation["forks"]),
                    # Older captures predate these fields; absent is unknown, not zero.
                    optional_count(observation.get("watchers")),
                    optional_count(observation.get("open_issues_and_prs")),
                )
            )
            for release in observation["releases"]:
                if not release.get("draft", False) and release.get("published_at"):
                    releases[str(release["id"])] = release
                    for asset in release.get("assets") or []:
                        tables["release_assets"].append(
                            (
                                repo,
                                f"{repo}:release:{release['id']}",
                                str(asset["id"]),
                                captured,
                                count(asset["download_count"]),
                            )
                        )
        for release_id, release in releases.items():
            tables["releases"].append(
                (
                    repo,
                    f"{repo}:release:{release_id}",
                    timestamp(release["published_at"]).date(),
                    "release",
                    release.get("name") or release["tag_name"],
                    release["html_url"],
                    bool(release.get("prerelease", False)),
                )
            )
        parse_signals(repo, folder / "signals", tables, warnings)
        tables["repositories"].append(
            (
                repo,
                f"github:{github_id}" if github_id is not None else f"name:{repo}",
                source["source_revision"],
                timestamp(manifest["synced_at"]),
            )
        )
    # Validate annotations before dbt casts or joins them.
    annotation_file = root / "seeds/annotations.csv"
    with annotation_file.open(newline="") as f:
        reader = csv.DictReader(f)
        expected = ["event_id", "repository", "event_date", "kind", "title", "url"]
        if reader.fieldnames != expected:
            raise ValueError(f"annotations.csv must have columns {expected}")
        ids = set()
        for row in reader:
            key = row["event_id"]
            if not key or key in ids or row["repository"] not in repositories:
                raise ValueError("annotations require unique IDs and configured repositories")
            ids.add(key)
            date.fromisoformat(row["event_date"])
            if not row["kind"] or not row["title"]:
                raise ValueError("annotations require kind and title")
    return tables, warnings


def parse_signals(repo: str, folder: Path, tables: dict, warnings: list[str]) -> None:
    """Optional aggregate signals; a missing signal is unavailable, never zero."""
    capture = read_json(folder / "capture.json")
    if not capture:
        warnings.append(f"{repo}: star, fork, issue, and package signals unavailable")
        return
    timestamp(capture["captured_at"])  # Reject a capture time without a UTC offset.
    for message in capture.get("errors", []):
        warnings.append(f"{repo}: {message}")
    for signal, filename, field in [
        ("stargazers", "stargazers.csv", "stars"),
        ("forks", "forks.csv", "forks"),
    ]:
        if signal not in capture:
            warnings.append(f"{repo}: {signal} history unavailable")
            continue
        seen = set()
        for r in csv_rows(folder / filename, ["date", field], warnings):
            day = date.fromisoformat(r["date"])
            if day in seen:
                raise ValueError(f"{filename}: duplicate date")
            seen.add(day)
            tables["stargazer_days" if signal == "stargazers" else "fork_days"].append(
                (repo, day, count(r[field]))
            )
        complete = bool(capture[signal]["complete"])
        if not complete:
            warnings.append(f"{repo}: {signal} listing truncated by GitHub pagination")
        tables["signal_captures"].append((repo, signal, signal_time(capture, signal), complete))
    if "issues" not in capture:
        warnings.append(f"{repo}: issue and pull request activity unavailable")
    else:
        parse_issues(repo, folder / "issues.csv", tables)
        tables["signal_captures"].append(
            (repo, "issues", signal_time(capture, "issues"), bool(capture["issues"]["complete"]))
        )
    for key in sorted(capture.get("packages", {})):
        registry, package = key.split(":", 1)
        seen = set()
        path = folder / "downloads" / registry / (package.replace("/", "__") + ".csv")
        for r in csv_rows(path, ["date", "downloads"], warnings):
            day = date.fromisoformat(r["date"])
            if day in seen:
                raise ValueError(f"{path.name}: duplicate date")
            seen.add(day)
            tables["package_downloads"].append(
                (repo, registry, package, day, count(r["downloads"]))
            )
        tables["signal_captures"].append(
            (repo, key, signal_time(capture["packages"], key, capture["captured_at"]), True)
        )


def signal_time(capture: dict, key: str, fallback: str | None = None) -> datetime:
    """A carried-forward signal keeps the time it was actually collected."""
    entry = capture.get(key) or {}
    return timestamp(entry.get("captured_at") or fallback or capture["captured_at"])


def parse_issues(repo: str, path: Path, tables: dict) -> None:
    numbers = set()
    required = ["number", "kind", "created_at", "closed_at", "merged_at", "author_association"]
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != required:
        raise ValueError(f"issues.csv must have columns {required}")
    for r in reader:
        number = count(r["number"])
        if number in numbers or r["kind"] not in {"issue", "pull_request"}:
            raise ValueError("issues.csv requires unique numbers and a known kind")
        if r["author_association"] not in ASSOCIATIONS:
            raise ValueError(f"issues.csv: unknown author association {r['author_association']}")
        if r["merged_at"] and r["kind"] != "pull_request":
            raise ValueError("issues.csv: only pull requests can be merged")
        numbers.add(number)
        tables["issues"].append(
            (
                repo,
                number,
                r["kind"],
                timestamp(r["created_at"]),
                optional_timestamp(r["closed_at"]),
                optional_timestamp(r["merged_at"]),
                r["author_association"],
            )
        )


def read(root: Path) -> duckdb.DuckDBPyConnection:
    """Read-only warehouse connection whose timestamps and date casts are UTC, like dbt's."""
    return duckdb.connect(
        str(root / "warehouse/analytics.duckdb"), read_only=True, config={"TimeZone": "UTC"}
    )


def load(root: Path, manifest: dict, database: Path) -> list[str]:
    tables, warnings = parse_inputs(root, manifest)
    database.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(database), config={"TimeZone": "UTC"}) as connection:
        connection.execute("begin transaction")
        connection.execute("create schema if not exists raw")
        for name, schema in SCHEMAS.items():
            connection.execute(f"create or replace table raw.{name} ({schema})")
            if tables[name]:
                placeholders = ",".join("?" for _ in tables[name][0])
                connection.executemany(
                    f"insert into raw.{name} values ({placeholders})", tables[name]
                )
        connection.execute("commit")
    return warnings

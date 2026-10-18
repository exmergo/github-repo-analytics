"""Portable command interface for maintainers and downstream agents."""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import duckdb
from pathlib import Path

from .io import SourceError
from .lifecycle import ValidationError


@contextlib.contextmanager
def workspace_lock(root: Path):
    import fcntl

    lock = root / ".data/workspace.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("w") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValidationError("another analytics command is using this workspace") from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def main():
    parser = argparse.ArgumentParser(description="Free open-source project analytics with Dex")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync", help="fetch immutable input revisions")
    sync.add_argument("--revision")
    sync.add_argument(
        "--data-repository", help="override input repository, e.g. this analytics repo in CI"
    )
    sync.add_argument("--no-supplement", action="store_true", help="import existing metadata only")
    candidate = sub.add_parser(
        "sync-candidate", help="CI: validate one unpublished multi-project commit"
    )
    candidate.add_argument("--revision", required=True)
    candidate.add_argument("--data-repository", required=True)
    for name in ["build", "check", "baseline", "questions", "events"]:
        sub.add_parser(name)
    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true", help="JSON is the default output")
    status.add_argument("--require-fresh", action="store_true")
    question = sub.add_parser("question", help="run a governed question recipe")
    question.add_argument("question")
    question.add_argument("--repository", required=True)
    for name in ["start", "end", "snapshot-date", "compare-date", "event-id"]:
        question.add_argument("--" + name)
    question.add_argument("--days", type=int, choices=[7, 28], default=7)
    metadata = sub.add_parser("collect-metadata", help="CI: append public totals and releases")
    metadata.add_argument("--repository", required=True)
    metadata.add_argument("--destination", required=True, type=Path)
    stage = sub.add_parser("stage", help="CI: import source and append supplemental metadata")
    stage.add_argument("--repository", required=True)
    stage.add_argument("--destination", required=True, type=Path)
    matrix = sub.add_parser("matrix", help="CI: generate source matrix")
    matrix.add_argument("--mode", choices=["collect", "all"], default="all")
    matrix.add_argument("--verify-public", action="store_true")
    publish = sub.add_parser("publish", help="CI: write validated publication metadata")
    publish.add_argument("--destination", type=Path, required=True)
    publish.add_argument("--data-commit", required=True)
    publish.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        with workspace_lock(root):
            result = dispatch(root, args)
        print(json.dumps({"status": "ok", "data": result}, default=str, indent=2))
    except (
        ValueError,
        TypeError,
        KeyError,
        OSError,
        SourceError,
        ValidationError,
        duckdb.Error,
    ) as exc:
        print(json.dumps({"status": "error", "errors": [str(exc)]}, default=str))
        return 1
    return 0


def dispatch(root, args):
    from . import lifecycle, sources
    from .config import load_sources

    if args.command == "sync":
        return sources.sync(
            root,
            revision=args.revision,
            data_repository=args.data_repository,
            supplement=not args.no_supplement,
        )
    if args.command == "sync-candidate":
        return sources.sync(
            root,
            revision=args.revision,
            data_repository=args.data_repository,
            supplement=False,
            internal_candidate=True,
        )
    if args.command in {"build", "check", "baseline"}:
        return getattr(lifecycle, args.command)(root)
    if args.command == "status":
        from .status import status

        result = status(root)
        if args.require_fresh and (
            not result["repositories"]
            or any(
                r["freshness"] != "fresh"
                or r["traffic_lag_days"] is None
                or r["traffic_lag_days"] > 3
                for r in result["repositories"]
            )
        ):
            raise ValidationError("one or more sources are stale; see status --json")
        return result
    if args.command == "questions":
        from .questions import RECIPES

        return RECIPES
    if args.command == "question":
        from .questions import answer

        return answer(
            root,
            args.question,
            args.repository,
            start=args.start,
            end=args.end,
            snapshot_date=args.snapshot_date,
            compare_date=args.compare_date,
            event_id=args.event_id,
            days=args.days,
        )
    if args.command == "events":
        import duckdb

        with duckdb.connect(str(root / "warehouse/analytics.duckdb"), read_only=True) as c:
            rows = c.execute(
                "select repository, event_id, event_date, kind, title, url, prerelease from dim_event order by event_date"
            ).fetchall()
        return [
            dict(
                zip(
                    ["repository", "event_id", "event_date", "kind", "title", "url", "prerelease"],
                    row,
                )
            )
            for row in rows
        ]
    if args.command == "collect-metadata":
        return sources.collect_metadata(root, args.repository, args.destination.resolve())
    if args.command == "stage":
        return sources.stage(root, args.repository, args.destination.resolve())
    if args.command == "matrix":
        if args.verify_public:
            import os

            sources.require_public_sources(root, destination=os.environ.get("GITHUB_REPOSITORY"))
        return {
            "include": [
                {"repository": s.repository, "mode": s.mode}
                for s in load_sources(root)
                if args.mode == "all" or s.mode == "collect"
            ]
        }
    if args.command == "publish":
        return lifecycle.publish(
            root, args.destination.resolve(), args.data_commit, args.code_commit
        )
    raise ValueError("unknown command")


if __name__ == "__main__":
    sys.exit(main())

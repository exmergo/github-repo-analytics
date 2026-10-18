"""Coverage and provenance for agent answers; never infer missing observations as zero."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb

from .io import read_json
from .lifecycle import code_digest


def status(root: Path, *, at: datetime | None = None) -> dict:
    at = at or datetime.now(timezone.utc)
    built = read_json(root / ".data/build.json")
    if not built or not (root / "warehouse/analytics.duckdb").exists():
        return {
            "ready": False,
            "reason": "run sync, build, baseline, and check",
            "repositories": [],
        }
    checked = read_json(root / ".data/check.json", {})
    digest = code_digest(root)
    validated = bool(
        built.get("validated")
        and built.get("code_digest") == digest
        and checked.get("code_digest") == digest
        and checked.get("input_directory") == built["inputs"]["directory"]
    )
    sources = {s["repository"]: s for s in built["inputs"]["sources"]}
    result = []
    with duckdb.connect(str(root / "warehouse/analytics.duckdb"), read_only=True) as connection:
        for repo, source in sources.items():
            dates = [
                r[0]
                for r in connection.execute(
                    "select date from fct_traffic where repository = ? order by date", [repo]
                ).fetchall()
            ]
            captures = connection.execute(
                "select max(captured_at) from fct_observations where repository = ?", [repo]
            ).fetchone()[0]
            snapshots = connection.execute(
                "select endpoint, max(captured_at) from fct_snapshot_status where repository = ? group by endpoint",
                [repo],
            ).fetchall()
            endpoint_captures = dict(snapshots)
            if captures:
                endpoint_captures["repository_totals"] = captures
            # A new totals capture must not conceal a stale traffic/discovery source.
            oldest = min(endpoint_captures.values(), default=None)
            # Updating a local checkout does not make a stale upstream observation fresh.
            age = max(0, (at - oldest).total_seconds() / 3600) if oldest else None
            interval = source.get("expected_refresh_hours", 24)
            freshness = (
                "unknown"
                if age is None
                else (
                    "critical"
                    if age > 168
                    else "warning"
                    if age > max(48, interval * 2)
                    else "fresh"
                )
            )
            observed = set(dates)
            gaps = (
                []
                if not dates
                else [
                    dates[0] + timedelta(days=i)
                    for i in range((dates[-1] - dates[0]).days + 1)
                    if dates[0] + timedelta(days=i) not in observed
                ]
            )
            eligible = [d for d in dates if d <= at.date() - timedelta(days=2)]
            result.append(
                {
                    "repository": repo,
                    "source_revision": source["source_revision"],
                    "source_data_repository": source.get("data_repository"),
                    "first_traffic_date": dates[0] if dates else None,
                    "last_traffic_date": dates[-1] if dates else None,
                    "latest_eligible_date": max(eligible) if eligible else None,
                    "missing_traffic_dates": gaps,
                    "observed_traffic_days": len(dates),
                    "traffic_lag_days": (at.date() - dates[-1]).days if dates else None,
                    "last_observed_totals_at": captures,
                    "latest_snapshots": dict(snapshots),
                    "endpoint_age_hours": {
                        name: round(max(0, (at - stamp).total_seconds() / 3600), 2)
                        for name, stamp in endpoint_captures.items()
                    },
                    "freshness": freshness,
                    "collection_age_hours": round(age, 2) if age is not None else None,
                }
            )
    return {
        "ready": validated,
        "reason": None if validated else "build and check the current definitions before answering",
        "built_at": built["built_at"],
        "checked_at": checked.get("checked_at"),
        "code_digest": digest,
        "synced_at": built["inputs"]["synced_at"],
        "warnings": built.get("warnings", []),
        "expected_unavailable_fields": checked.get("expected_nullable_fields", {}),
        "repositories": result,
    }


def coverage(root: Path, repository: str, start: date, end: date) -> dict:
    if end <= start:
        raise ValueError("end must be after start (end is exclusive)")
    if (end - start).days > 3660:
        raise ValueError("comparison windows are limited to ten years")
    with duckdb.connect(str(root / "warehouse/analytics.duckdb"), read_only=True) as connection:
        observed = {
            r[0]
            for r in connection.execute(
                "select date from fct_traffic where repository = ? and date >= ? and date < ?",
                [repository, start, end],
            ).fetchall()
        }
    expected = {start + timedelta(days=i) for i in range((end - start).days)}
    recent = sorted(
        d for d in expected if d > datetime.now(timezone.utc).date() - timedelta(days=2)
    )
    return {
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "observed_days": len(observed),
        "expected_days": len(expected),
        "missing_dates": sorted(expected - observed),
        "recent_unsettled_dates": recent,
        "complete": expected == observed and not recent,
    }

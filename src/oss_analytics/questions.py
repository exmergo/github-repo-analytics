"""Executable MetricFlow recipes. Metric definitions remain in semantic YAML."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from .lifecycle import ValidationError, dex

METRICS = [
    "views",
    "clones",
    "visitor_days",
    "cloner_days",
    "observed_traffic_days",
    "views_per_visitor_day",
    "clones_per_cloner_day",
    "stars_observed",
    "forks_observed",
    "stars_net_change",
    "forks_net_change",
    "legacy_stars_cumulative",
    "legacy_forks_cumulative",
    "referrer_views_14d",
    "referrer_visitor_observations_14d",
    "path_views_14d",
    "path_visitor_observations_14d",
]


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def query(
    root: Path,
    metrics: str,
    repository: str,
    *,
    start=None,
    end=None,
    snapshot_date=None,
    group_by=None,
    items=None,
) -> dict:
    where = "{{ Dimension('repository__name') }} = " + literal(repository)
    if snapshot_date:
        start = snapshot_date
        end = date.fromisoformat(snapshot_date) + timedelta(days=1)
    if start:
        where += " AND {{ TimeDimension('metric_time', 'day') }} >= " + literal(str(start))
    if end:
        where += " AND {{ TimeDimension('metric_time', 'day') }} < " + literal(str(end))
    if items is not None:
        dimension, names = items
        where += " AND " + (
            "{{ Dimension('"
            + dimension
            + "') }} IN ("
            + ", ".join(literal(name) for name in names)
            + ")"
            if names
            else "1 = 0"
        )
    args = ["explore", "semantic", "query", metrics, "--local", "--where", where]
    if group_by:
        args += ["--group-by", group_by]
    result = dex(root, *args)
    if result.get("data", {}).get("truncated"):
        raise ValidationError("metric result was truncated; narrow the query")
    return result


RECIPES = {
    "traffic": "Views and clones over a covered period",
    "traffic-trend": "Daily views and clone series",
    "audience": "Visitor-days and cloner-days; not period-unique people",
    "engagement": "Views per visitor-day and clones per cloner-day",
    "growth": "Consecutive complete 7-day or 28-day traffic windows",
    "stars": "Last observed star and fork totals",
    "star-growth": "Daily net observed star/fork changes; gaps stay null",
    "legacy-growth": "Upstream reconstructed historical star/fork totals",
    "referrers": "Reported sources in an exact rolling snapshot",
    "paths": "Reported content in an exact rolling snapshot",
    "referrer-change": "Compare two exact reported-referrer snapshots",
    "path-change": "Compare two exact popular-content snapshots",
    "event-impact": "Seven complete days before and after a release or annotation",
    "active-users": "Unavailable: GitHub activity does not measure active users",
}


def answer(
    root: Path,
    question: str,
    repository: str,
    *,
    start=None,
    end=None,
    snapshot_date=None,
    compare_date=None,
    event_id=None,
    days=7,
) -> dict:
    import duckdb
    from datetime import datetime, timezone
    from .status import coverage, status

    evidence = status(root)
    if question not in RECIPES:
        raise ValueError("unknown question; use oss-analytics questions")
    matching = [r for r in evidence["repositories"] if r["repository"] == repository]
    if not matching:
        raise ValueError("repository is not in the built dataset")
    record = matching[0]
    response = {
        "question": question,
        "repository": repository,
        "definition": RECIPES[question],
        "evidence": evidence,
    }
    if question == "active-users":
        return {
            **response,
            "available": False,
            "reason": "No active-user or installation source is collected. Clones, views, and stars cannot answer this question.",
        }
    if not evidence["ready"]:
        raise ValidationError(
            "dataset or definitions have changed: build, review baseline, and check before answering"
        )
    if days not in {7, 28}:
        raise ValueError("days must be 7 or 28")
    if question in {"referrers", "paths", "referrer-change", "path-change"}:
        kind = "referrer" if question.startswith("referrer") else "path"
        endpoint = "referrers" if kind == "referrer" else "paths"
        if not snapshot_date:
            raise ValueError("discovery questions require --snapshot-date YYYY-MM-DD")
        selected = [snapshot_date]
        if question.endswith("-change"):
            if not compare_date or compare_date == snapshot_date:
                raise ValueError("snapshot comparisons require a different --compare-date")
            selected.append(compare_date)
        return discovery_answer(root, response, repository, kind, endpoint, selected)

    if question in {"stars", "star-growth", "legacy-growth"}:
        metrics = {
            "stars": "stars_observed,forks_observed",
            "star-growth": "stars_net_change,forks_net_change",
            "legacy-growth": "legacy_stars_cumulative,legacy_forks_cumulative",
        }[question]
        if (start is None) != (end is None):
            raise ValueError("provide both --start and --end")
        if start and date.fromisoformat(end) <= date.fromisoformat(start):
            raise ValueError("end must be after start")
        result = query(
            root,
            metrics,
            repository,
            start=start,
            end=end,
            group_by="metric_time" if question == "star-growth" else None,
        )
        columns = result["data"]["columns"]
        indexes = [columns.index(m) for m in metrics.split(",")]
        available = any(row[i] is not None for row in result["data"]["cells"] for i in indexes)
        return {
            **response,
            "available": available,
            "result": result,
            "reason": None
            if available
            else "No observations support this metric in the requested period yet.",
            "interpretation": "Observed totals are captured snapshots. Net daily changes require consecutive captures. Legacy history is reconstructed and may change on reimport.",
        }

    eligible = record["latest_eligible_date"]
    if not eligible:
        return {**response, "available": False, "reason": "No eligible traffic dates"}
    end_date = date.fromisoformat(end) if end else eligible + timedelta(days=1)
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=days)
    if question == "event-impact":
        if not event_id:
            raise ValueError("event-impact requires --event-id; use oss-analytics events")
        with duckdb.connect(str(root / "warehouse/analytics.duckdb"), read_only=True) as connection:
            event = connection.execute(
                "select event_date, prerelease from dim_event where repository = ? and event_id = ?",
                [repository, event_id],
            ).fetchone()
            if event is None:
                raise ValueError("event ID does not exist for this repository")
            # Explicit event selection is also the opt-in for a prerelease.
            day = event[0]
            overlaps = connection.execute(
                "select event_id, event_date from dim_event where repository = ? and event_id <> ? and event_date >= ? and event_date < ?",
                [repository, event_id, day - timedelta(days=7), day + timedelta(days=8)],
            ).fetchall()
        periods = [
            (day - timedelta(days=7), day),
            (day + timedelta(days=1), day + timedelta(days=8)),
        ]
        response["event_id"] = event_id
        response["overlapping_events"] = overlaps
        response["interpretation"] = (
            "Association only; the event day is excluded. Other events and automated traffic may influence these counts."
        )
    elif question == "growth":
        if start:
            raise ValueError("growth uses --end and --days; omit --start")
        periods = [
            (end_date - timedelta(days=2 * days), end_date - timedelta(days=days)),
            (end_date - timedelta(days=days), end_date),
        ]
    else:
        periods = [(start_date, end_date)]
    coverages = [coverage(root, repository, a, b) for a, b in periods]
    response["coverage"] = coverages
    if not all(c["complete"] for c in coverages):
        return {
            **response,
            "available": False,
            "reason": "A requested calendar window is incomplete or recent; no shortened comparison was substituted.",
        }
    metrics = {
        "audience": "visitor_days,cloner_days",
        "engagement": "views_per_visitor_day,clones_per_cloner_day",
    }.get(question, "views,clones")
    results = [
        query(
            root,
            metrics,
            repository,
            start=a,
            end=b,
            group_by="metric_time" if question == "traffic-trend" else None,
        )
        for a, b in periods
    ]
    response.update({"available": True, "results": results})
    if len(results) == 2:
        before = result_values(results[0])
        after = result_values(results[1])
        response["changes"] = {
            metric: {
                "absolute": after[metric] - before[metric],
                "percent": None
                if before[metric] == 0
                else 100 * (after[metric] - before[metric]) / before[metric],
            }
            for metric in ["views", "clones"]
        }
    response["as_of"] = datetime.now(timezone.utc)
    return response


def result_values(envelope: dict) -> dict:
    """Read Dex's columnar payload, checking its shape before computing comparisons."""
    data = envelope["data"]
    columns, cells = data.get("columns", []), data.get("cells", [])
    if data.get("row_count") != 1:
        raise ValidationError("expected exactly one aggregate row for the comparison")
    if len(cells) == len(columns) and all(isinstance(c, list) and len(c) == 1 for c in cells):
        return dict(zip(columns, (c[0] for c in cells)))
    if len(cells) == 1 and len(cells[0]) == len(columns):
        return dict(zip(columns, cells[0]))
    raise ValidationError("unexpected Dex result shape")


def discovery_answer(root, response, repository, kind, endpoint, selected):
    """Use source item names as vocabulary, and MetricFlow for every reported count."""
    import duckdb

    days = [date.fromisoformat(str(day)) for day in selected]
    captures = []
    with duckdb.connect(str(root / "warehouse/analytics.duckdb"), read_only=True) as connection:
        for day in days:
            row = connection.execute(
                "select captured_at from fct_snapshot_status where repository = ? and endpoint = ? and date = ?",
                [repository, endpoint, day],
            ).fetchone()
            if row is None:
                return {
                    **response,
                    "available": False,
                    "reason": f"No successful {endpoint} snapshot on {day}; no neighboring date was substituted.",
                }
            captures.append(row[0])
        placeholders = ",".join("?" for _ in days)
        # Limit vocabulary to the union of these top-10 snapshots, keeping result sets bounded.
        items = [
            r[0]
            for r in connection.execute(
                f"select distinct {kind} from fct_{kind} where repository = ? and date in ({placeholders}) and is_reported order by {kind}",
                [repository, *days],
            ).fetchall()
        ]
    results = []
    for day, capture in zip(days, captures):
        envelope = query(
            root,
            f"{kind}_views_14d,{kind}_visitor_observations_14d",
            repository,
            snapshot_date=str(day),
            group_by=f"{kind}_row__{kind}",
            items=(f"{kind}_row__{kind}", items),
        )
        columns = envelope["data"]["columns"]
        values = [dict(zip(columns, r)) for r in envelope["data"]["cells"]]
        reported = sorted(
            (r for r in values if r[f"{kind}_views_14d"] is not None),
            key=lambda r: (-r[f"{kind}_views_14d"], r[f"{kind}_row__{kind}"]),
        )
        rankings = {}
        previous_count, rank = None, 0
        for position, row in enumerate(reported, 1):
            count = row[f"{kind}_views_14d"]
            if count != previous_count:
                rank = position
            rankings[row[f"{kind}_row__{kind}"]] = {"views": count, "rank": rank}
            previous_count = count
        results.append(
            {
                "snapshot_date": day,
                "captured_at": capture,
                "query": envelope,
                "reported_item_count": len(reported),
                "rankings": rankings,
            }
        )
    changes = {}
    if len(results) == 2:
        for item in items:
            before = results[0]["rankings"].get(item)
            after = results[1]["rankings"].get(item)
            changes[item] = {
                "before": before,
                "after": after,
                "views_change": after["views"] - before["views"] if before and after else None,
                "rank_change": after["rank"] - before["rank"] if before and after else None,
            }
    return {
        **response,
        "available": True,
        "snapshots": results,
        "item_changes": changes,
        "windows_overlap": abs(captures[0] - captures[-1]) < timedelta(days=14)
        if len(captures) > 1
        else None,
        "interpretation": "Each capture reports GitHub's rolling top 10. Missing entries are unreported, not zero. Ranks are computed from returned counts; a negative rank change is an improvement. Overlapping rolling windows are not additive.",
    }

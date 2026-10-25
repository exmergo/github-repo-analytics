"""Executable MetricFlow recipes. Metric definitions remain in semantic YAML."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .lifecycle import ValidationError, dex
from .warehouse import read as read_warehouse

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
    "watchers_observed",
    "open_issues_and_prs_observed",
    "legacy_stars_change",
    "legacy_forks_change",
    "events",
    "stars_gained",
    "forks_created",
    "stars_from_history",
    "issues_opened",
    "issues_closed",
    "prs_opened",
    "prs_merged",
    "first_time_contributor_prs",
    "median_hours_to_merge",
    "deployments",
    "median_hours_lead_time",
    "release_downloads",
    "release_downloads_net_change",
    "package_downloads",
    "pypi_downloads",
    "npm_downloads",
    "views_28d",
    "views_wow_growth",
    "stars_gained_wow_growth",
]
# Windowed cumulative and offset metrics are only defined over a time axis.
TIME_METRICS = {"views_28d": "week", "views_wow_growth": "week", "stars_gained_wow_growth": "week"}
COMMUNITY = (
    "issues_opened,issues_closed,prs_opened,prs_merged,first_time_contributor_prs,"
    "median_hours_to_merge"
)


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def query(
    root: Path,
    metrics: str,
    repository: str | None,
    *,
    start=None,
    end=None,
    snapshot_date=None,
    group_by=None,
    items=None,
    grain=None,
) -> dict:
    """One governed query; repository=None compares every tracked repository."""
    clauses = []
    if repository:
        clauses.append("{{ Dimension('repository__name') }} = " + literal(repository))
    if snapshot_date:
        start = snapshot_date
        end = date.fromisoformat(snapshot_date) + timedelta(days=1)
    if start:
        clauses.append("{{ TimeDimension('metric_time', 'day') }} >= " + literal(str(start)))
    if end:
        clauses.append("{{ TimeDimension('metric_time', 'day') }} < " + literal(str(end)))
    if items is not None:
        dimension, names = items
        clauses.append(
            "{{ Dimension('"
            + dimension
            + "') }} IN ("
            + ", ".join(literal(name) for name in names)
            + ")"
            if names
            else "1 = 0"
        )
    args = ["explore", "semantic", "query", metrics, "--local"]
    if clauses:
        args += ["--where", " AND ".join(clauses)]
    if group_by:
        args += ["--group-by", group_by]
    if grain:
        args += ["--grain", grain]
    result = dex(root, *args)
    if result.get("data", {}).get("truncated"):
        raise ValidationError("metric result was truncated; narrow the query")
    return result


def rows(envelope: dict) -> list[dict]:
    data = envelope["data"]
    return [dict(zip(data["columns"], row)) for row in data.get("cells", [])]


def has_values(envelope: dict, metrics: str) -> bool:
    return any(r.get(m) is not None for r in rows(envelope) for m in metrics.split(","))


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
    "event-impact": "Complete 7- or 28-day windows before and after a release or annotation",
    "star-history": "Stars and forks gained per day/week/month from current stargazers",
    "community": "Issues and PRs opened, closed, merged; first-time contributors; time to merge",
    "release-downloads": "GitHub release asset downloads by release",
    "package-downloads": "PyPI/npm downloads for configured packages (optional add-on)",
    "compare": "One window across every tracked repository",
    "referrer-trend": "Current top referrers, latest snapshot per week; windows never summed",
    "weekly-report": "Last complete week: traffic growth, stars, community, downloads",
    "deployments": "Production deployments and median merge-to-deployment lead time",
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
    grain="week",
) -> dict:
    from .status import coverage, status

    evidence = status(root)
    if question not in RECIPES:
        raise ValueError("unknown question; use oss-analytics questions")
    if question == "compare":
        repository = None
    elif not repository:
        raise ValueError("this question requires --repository")
    matching = [r for r in evidence["repositories"] if r["repository"] == repository]
    if repository and not matching:
        raise ValueError("repository is not in the built dataset")
    record = matching[0] if matching else None
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
    if days not in {7, 14, 28, 91}:
        raise ValueError("days must be 7, 14, 28, or 91")
    if question in {"growth", "engagement", "event-impact"} and days not in {7, 28}:
        raise ValueError("comparison windows must be 7 or 28 days")
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
            group_by=None if question == "stars" else "metric_time",
            grain=None if question == "stars" else grain,
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

    if question == "deployments":
        return deployment_answer(root, response, repository, record, start, end, days, grain)

    if question in {"star-history", "community", "release-downloads", "package-downloads"}:
        return signal_answer(root, response, question, repository, record, start, end, days, grain)
    if question == "weekly-report":
        return weekly_report(root, response, repository, record)

    if question == "compare":
        eligible = min(
            (
                r["latest_eligible_date"]
                for r in evidence["repositories"]
                if r["latest_eligible_date"]
            ),
            default=None,
        )
        if not eligible:
            return {**response, "available": False, "reason": "No eligible traffic dates"}
        end_date = date.fromisoformat(end) if end else eligible + timedelta(days=1)
        start_date = date.fromisoformat(start) if start else end_date - timedelta(days=days)
        coverages = {
            r["repository"]: coverage(root, r["repository"], start_date, end_date)
            for r in evidence["repositories"]
        }
        metrics = "views,clones,visitor_days,stars_gained,prs_merged,package_downloads"
        result = query(
            root, metrics, None, start=start_date, end=end_date, group_by="repository__name"
        )
        return {
            **response,
            "available": True,
            "traffic_coverage": coverages,
            "result": result,
            "interpretation": "Traffic for a repository with incomplete coverage is not comparable; check traffic_coverage. Null means the source is not collected for that repository, not zero.",
        }

    if question == "referrer-trend":
        return referrer_trend(root, response, repository, start, end)

    eligible = record["latest_eligible_date"]
    if not eligible:
        return {**response, "available": False, "reason": "No eligible traffic dates"}
    end_date = date.fromisoformat(end) if end else eligible + timedelta(days=1)
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=days)
    if question == "event-impact":
        if not event_id:
            raise ValueError("event-impact requires --event-id; use oss-analytics events")
        with read_warehouse(root) as connection:
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
                [repository, event_id, day - timedelta(days=days), day + timedelta(days=days + 1)],
            ).fetchall()
        periods = [
            (day - timedelta(days=days), day),
            (day + timedelta(days=1), day + timedelta(days=days + 1)),
        ]
        response["event_id"] = event_id
        response["overlapping_events"] = overlaps
        response["interpretation"] = (
            "Association only; the event day is excluded. Other events and automated traffic may influence these counts."
        )
    elif question in {"growth", "engagement"}:
        if start:
            raise ValueError(f"{question} uses --end and --days; omit --start")
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
            grain=grain if question == "traffic-trend" else None,
        )
        for a, b in periods
    ]
    response.update({"available": True, "results": results})
    if len(results) == 2:
        before = result_values(results[0])
        after = result_values(results[1])
        response["changes"] = {
            metric: {
                "absolute": None
                if before[metric] is None or after[metric] is None
                else after[metric] - before[metric],
                "percent": None
                if not before[metric] or after[metric] is None
                else 100 * (after[metric] - before[metric]) / before[metric],
            }
            for metric in metrics.split(",")
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

    days = [date.fromisoformat(str(day)) for day in selected]
    captures = []
    with read_warehouse(root) as connection:
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


def signal_coverage(root: Path, repository: str) -> dict:
    """Which optional signals exist, when they were captured, and whether they are complete."""

    with read_warehouse(root) as c:
        captures = {
            r[0]: {"captured_at": r[1], "complete": r[2]}
            for r in c.execute(
                "select signal, captured_at, complete from stg_signal_captures where repository = ?",
                [repository],
            ).fetchall()
        }
        # The last complete day per signal; capture days are partial and are excluded.
        through = {
            "star-history": c.execute(
                "select max(date) from fct_star_history where repository = ?", [repository]
            ).fetchone()[0],
            "community": c.execute(
                "select cast(captured_at at time zone 'UTC' as date) - 1 from stg_signal_captures where repository = ? and signal = 'issues'",
                [repository],
            ).fetchone(),
            "package-downloads": c.execute(
                "select max(date) from fct_package_downloads where repository = ?", [repository]
            ).fetchone()[0],
        }
        through["community"] = through["community"][0] if through["community"] else None
        assets = c.execute(
            "select count(*) from fct_release_downloads where repository = ?", [repository]
        ).fetchone()[0]
    return {"signals": captures, "complete_through": through, "release_asset_rows": assets}


def signal_answer(root, response, question, repository, record, start, end, days, grain):
    from .config import load_sources

    signals = signal_coverage(root, repository)
    response["signal_coverage"] = signals
    if (start is None) != (end is None):
        raise ValueError("provide both --start and --end")
    if start and date.fromisoformat(end) <= date.fromisoformat(start):
        raise ValueError("end must be after start")
    if question == "star-history":
        required = "stargazers"
        metrics = "stars_gained,forks_created,stars_from_history"
        group_by, use_grain = "metric_time", grain
        reason = "Star history is collected by sync/stage from the stargazers API."
    elif question == "community":
        required = "issues"
        metrics = COMMUNITY
        group_by, use_grain = ("metric_time", grain) if start else (None, None)
        reason = "Issue and pull request activity is collected by sync/stage."
    elif question == "release-downloads":
        required = None
        metrics = "release_downloads"
        group_by, use_grain = "event__title", None
        reason = "This repository has no release assets captured; GitHub counts downloads only for uploaded assets, not source archives."
        if not signals["release_asset_rows"]:
            return {**response, "available": False, "reason": reason}
    else:
        configured = [s.package_list() for s in load_sources(root) if s.repository == repository]
        if not configured or not configured[0]:
            return {
                **response,
                "available": False,
                "reason": "No packages configured for this repository. Add packages: {pypi: [...]} or {npm: [...]} in sources.yml.",
            }
        required = None
        metrics = "package_downloads"
        group_by, use_grain = (
            "package_download__registry,package_download__package,metric_time",
            grain,
        )
        reason = "No downloads were reported for the configured packages in this period."
    if required and required not in signals["signals"]:
        return {**response, "available": False, "reason": reason}
    if not start and question != "release-downloads":
        # Default: the last N days ending at this signal's last complete day, never "today".
        last = signals["complete_through"][question]
        if last is None:
            return {**response, "available": False, "reason": reason}
        end = str(last + timedelta(days=1))
        start = str(last + timedelta(days=1) - timedelta(days=days))
    last = signals["complete_through"].get(question)
    if required and (last is None or date.fromisoformat(end) - timedelta(days=1) > last):
        return {
            **response,
            "available": False,
            "reason": f"The window extends past the last completely collected day ({last}); no shorter window was substituted.",
        }
    result = query(
        root, metrics, repository, start=start, end=end, group_by=group_by, grain=use_grain
    )
    # Inside proven coverage, an empty count is zero activity; registry and asset gaps are not.
    available = bool(required) or has_values(result, metrics)
    return {
        **response,
        "available": available,
        "period": {"start": start, "end_exclusive": end},
        "zero_when_null": bool(required),
        "result": result,
        "reason": None if available else reason,
        "interpretation": INTERPRETATIONS[question],
    }


INTERPRETATIONS = {
    "star-history": "Stars are dated by when current stargazers starred; people who unstarred are invisible, so past totals are lower bounds of past interest. The partial capture day is excluded. Within this covered window, a null count means no stars that period.",
    "community": "Counts are by event date (opened, closed, merged); within this covered window a null count means no activity. First-time contributor PRs use GitHub's association when collection first saw the PR; backfilled history undercounts. Median time to merge covers PRs merged in the period.",
    "release-downloads": "Cumulative asset downloads at the latest capture. Downloads are not unique users or installations, and source archives are not counted by GitHub.",
    "package-downloads": "Registry downloads include CI and mirrors-excluded bots; they are not installations or users. Registries revise recent days.",
}


def referrer_trend(root, response, repository, start, end):
    """Latest snapshot per 7-day window; MetricFlow's non-additive axis picks that snapshot."""

    if (start is None) != (end is None):
        raise ValueError("provide both --start and --end")
    with read_warehouse(root) as c:
        bounds = c.execute(
            "select min(date), max(date) from fct_snapshot_status where repository = ? and endpoint = 'referrers'",
            [repository],
        ).fetchone()
        if bounds[1] is None:
            return {**response, "available": False, "reason": "No referrer snapshots"}
        end = end or str(bounds[1] + timedelta(days=1))
        start = start or str(date.fromisoformat(end) - timedelta(days=42))
        # Follow the latest reported top 10 back in time. The dense grid keeps every snapshot
        # date for every item, so naming items cannot change which snapshot is latest.
        items = [
            r[0]
            for r in c.execute(
                """select referrer from fct_referrer
                   where repository = ? and is_reported
                     and date = (select max(date) from fct_referrer
                                 where repository = ? and is_reported and date < ?)
                   order by referrer""",
                [repository, repository, end],
            ).fetchall()
        ]
    # One bounded query per window keeps each result within Dex's row cap.
    windows = []
    window_end = date.fromisoformat(end)
    while window_end > date.fromisoformat(start):
        window_start = max(window_end - timedelta(days=7), date.fromisoformat(start))
        envelope = query(
            root,
            "referrer_views_14d",
            repository,
            start=window_start,
            end=window_end,
            group_by="referrer_row__referrer",
            items=("referrer_row__referrer", items),
        )
        windows.append(
            {
                "start": str(window_start),
                "end_exclusive": str(window_end),
                "views_14d": {
                    r["referrer_row__referrer"]: r["referrer_views_14d"] for r in rows(envelope)
                },
            }
        )
        window_end = window_start
    return {
        **response,
        "available": bool(items),
        "period": {"start": start, "end_exclusive": end},
        "referrers": items,
        "windows": windows[::-1],
        "interpretation": "Each window shows the latest rolling 14-day top-10 snapshot inside it; consecutive windows overlap and are never additive. Null is unreported, not zero.",
    }


def weekly_report(root, response, repository, record):
    """A maintainer digest built only from the governed recipes above."""
    sections = {}
    for name, kwargs in [
        ("traffic_growth", {"question": "growth", "days": 7}),
        ("star_history", {"question": "star-history", "days": 14, "grain": "week"}),
        ("community", {"question": "community", "days": 7}),
        ("release_downloads", {"question": "release-downloads"}),
        ("package_downloads", {"question": "package-downloads", "days": 14, "grain": "week"}),
    ]:
        try:
            result = answer(root, repository=repository, **kwargs)
        except (ValueError, ValidationError) as exc:
            result = {"available": False, "reason": str(exc)}
        result.pop("evidence", None)
        sections[name] = result
    return {
        **response,
        "available": any(s.get("available") for s in sections.values()),
        "sections": sections,
        "interpretation": "Each section states its own window and coverage. Unavailable sections are reported, not filled with zero.",
    }


def deployment_answer(root, response, repository, record, start, end, days, grain):
    """Shipping evidence is observed history; absent evidence is never an inferred zero."""
    signal = record["signals"].get("deployments")
    if (start is None) != (end is None):
        raise ValueError("provide both --start and --end")
    if not signal:
        return {
            **response,
            "available": False,
            "reason": "No deployment capture. Configure deployments: {source: github, environment: production} and sync/build/check.",
        }
    if not signal["complete"]:
        return {
            **response,
            "available": False,
            "reason": "Deployment/status or merged-PR evidence is incomplete; no smaller comparison was substituted.",
        }
    captured = signal["captured_at"]
    end_date = date.fromisoformat(end) if end else captured.date()
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=days)
    if end_date <= start_date:
        raise ValueError("end must be after start")
    if end_date > captured.date():
        return {
            **response,
            "available": False,
            "reason": "The requested window includes the partial capture day or later; no shorter window was substituted.",
        }
    metrics = "deployments,median_hours_lead_time"
    result = query(
        root,
        metrics,
        repository,
        start=start_date,
        end=end_date,
        group_by="metric_time",
        grain=grain,
    )
    return {
        **response,
        "available": has_values(result, metrics),
        "period": {"start": start_date, "end_exclusive": end_date},
        "capture": signal,
        "zero_when_null": False,
        "result": result,
        "reason": None
        if has_values(result, metrics)
        else "No observed successful deployments in this window; absent evidence was not replaced by zero.",
        "units": {"deployments": "deployments", "median_hours_lead_time": "hours"},
        "interpretation": "Observed GitHub deployment history in the explicitly configured environment. Counts include redeployments; lead time is a per-PR median from merge to its first observed successful containing deployment, grouped by shipping date. Missing statuses, deleted records and unobserved earlier deployments limit historical completeness. Unmapped PRs and null medians are not zero. Capture UTC day excluded.",
    }

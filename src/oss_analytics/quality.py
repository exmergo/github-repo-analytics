"""Explain expected nulls from source coverage, without clearing Dex findings globally."""

from pathlib import Path

import duckdb


def expected_nullable_fields(root: Path) -> dict[str, str]:
    """Only source-proven absences qualify; every other high-severity finding still blocks."""
    expected = {}
    with duckdb.connect(str(root / "warehouse/analytics.duckdb"), read_only=True) as c:
        pairs, consecutive = c.execute("""
            with days as (
                select distinct repository, cast(captured_at at time zone 'UTC' as date) as day from raw.observations
            ), gaps as (
                select day, lag(day) over (partition by repository order by day) as previous_day
                from days
            )
            select count(previous_day), count(*) filter (where day - previous_day = 1) from gaps
        """).fetchone()
        if not pairs:
            expected["main.fct_observations.observation_gap_days"] = (
                "No repository has two daily captures yet"
            )
        if not consecutive:
            for column in ["stars_net_change", "forks_net_change"]:
                expected["main.fct_observations." + column] = (
                    "No consecutive daily source captures exist"
                )
        for column in ["stars", "forks"]:
            if c.execute(f"select count({column}) from raw.legacy").fetchone()[0] == 0:
                for relation in ["raw.legacy", "main.stg_legacy", "main.fct_legacy"]:
                    expected[relation + "." + column] = (
                        "This upstream historical series is unavailable"
                    )
        for endpoint, kind in [("referrers", "referrer"), ("paths", "path")]:
            reported = c.execute(
                """
                select count(*) from raw.discovery d join fct_snapshot_status s
                  on d.repository = s.repository and d.endpoint = s.endpoint
                 and d.captured_at = s.captured_at
                where s.endpoint = ?
            """,
                [endpoint],
            ).fetchone()[0]
            if not reported:
                for column in ["views", "uniques", "reported_rank"]:
                    expected[f"main.fct_{kind}.{column}"] = (
                        "Selected daily snapshots have no reported items"
                    )
        annotation_urls = c.execute("select count(url) from annotations").fetchone()[0]
        if not annotation_urls:
            expected["main.annotations.url"] = "Annotation URLs are optional and none were supplied"
            if c.execute("select count(url) from raw.releases").fetchone()[0] == 0:
                expected["main.dim_event.url"] = "No event source supplied a URL"
    return expected

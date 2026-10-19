"""Explain expected nulls from source coverage, without clearing Dex findings globally."""

from pathlib import Path

from .warehouse import read as read_warehouse


def expected_nullable_fields(root: Path) -> dict[str, str]:
    """Only source-proven absences qualify; every other high-severity finding still blocks."""
    expected = {}
    with read_warehouse(root) as c:
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
        for column in ["watchers", "open_issues_and_prs"]:
            if c.execute(f"select count({column}) from raw.observations").fetchone()[0] == 0:
                for relation in [
                    "raw.observations",
                    "main.stg_observations",
                    "main.fct_observations",
                ]:
                    expected[relation + "." + column] = (
                        "Every capture predates this field; it is filled from the next collection"
                    )
        for column in ["stars", "forks"]:
            # A change needs two reported values of the same series in one repository.
            series = c.execute(
                f"select count(*) from (select repository from raw.legacy where {column} is not null"
                " group by repository having count(*) > 1)"
            ).fetchone()[0]
            if not series:
                expected[f"main.fct_legacy.{column}_change"] = (
                    "No repository has two historical values in this series"
                )
        closed, merged = c.execute(
            "select count(closed_at), count(merged_at) from raw.issues"
        ).fetchone()
        if not closed:
            expected["main.stg_issues.closed_at"] = "No collected issue or pull request is closed"
            expected["main.fct_issues.closed_date"] = "No collected issue or pull request is closed"
        if not merged:
            for field in [
                "main.stg_issues.merged_at",
                "main.fct_issues.merged_date",
                "main.fct_issues.hours_to_merge",
            ]:
                expected[field] = "No collected pull request is merged"
        consecutive_assets = c.execute(
            "select count(downloads_net_change) from fct_release_downloads"
        ).fetchone()[0]
        if not consecutive_assets:
            expected["main.fct_release_downloads.downloads_net_change"] = (
                "No release asset has consecutive daily captures yet"
            )
        annotation_urls = c.execute("select count(url) from annotations").fetchone()[0]
        if not annotation_urls:
            expected["main.annotations.url"] = "Annotation URLs are optional and none were supplied"
            if c.execute("select count(url) from raw.releases").fetchone()[0] == 0:
                expected["main.dim_event.url"] = "No event source supplied a URL"
    return expected

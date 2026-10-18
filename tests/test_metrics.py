from datetime import date
import duckdb
import pytest

from oss_analytics.lifecycle import dex
from oss_analytics.questions import METRICS, answer, query, result_values
from oss_analytics.status import coverage


def rows(result):
    return [dict(zip(result["data"]["columns"], r)) for r in result["data"]["cells"]]


def test_additive_ratios_and_repository_isolation(project):
    values = result_values(
        query(
            project,
            "views,clones,visitor_days,cloner_days,observed_traffic_days,views_per_visitor_day",
            "exmergo/dex",
            start="2026-07-01",
            end="2026-07-08",
        )
    )
    assert values == {
        "views": 70,
        "clones": 28,
        "visitor_days": 21,
        "cloner_days": 14,
        "observed_traffic_days": 7,
        "views_per_visitor_day": pytest.approx(10 / 3),
    }
    assert result_values(query(project, "views", "example/other"))["views"] == 660
    result = dex(
        project,
        "explore",
        "semantic",
        "query",
        "views,stars_observed",
        "--group-by",
        "repository__name",
        "--local",
    )
    assert {r["repository__name"]: (r["views"], r["stars_observed"]) for r in rows(result)} == {
        "exmergo/dex": (600, 9),
        "example/other": (660, 10),
    }


def test_path_snapshot_isolation(project):
    assert (
        result_values(query(project, "path_views_14d", "exmergo/dex", snapshot_date="2026-07-02"))[
            "path_views_14d"
        ]
        == 22
    )
    assert (
        result_values(
            query(project, "path_views_14d", "example/other", snapshot_date="2026-07-02")
        )["path_views_14d"]
        == 23
    )
    compared = answer(
        project,
        "referrer-change",
        "exmergo/dex",
        snapshot_date="2026-07-01",
        compare_date="2026-07-02",
    )
    assert compared["item_changes"]["Google"]["views_change"] == 11
    assert compared["item_changes"]["gone.example"]["views_change"] is None


def test_totals_latest_not_maximum_and_missing_changes(project):
    values = result_values(
        query(
            project,
            "stars_observed,forks_observed",
            "exmergo/dex",
            start="2026-07-01",
            end="2026-07-03",
        )
    )
    assert values == {"stars_observed": 8, "forks_observed": 2}
    result = query(project, "stars_net_change", "exmergo/dex", group_by="metric_time")
    values = {str(r["metric_time__day"])[:10]: r["stars_net_change"] for r in rows(result)}
    assert values == {"2026-07-01": None, "2026-07-02": -2, "2026-07-04": None}


def test_snapshot_latest_per_day_no_resurrection(project):
    result = query(
        project,
        "referrer_views_14d",
        "exmergo/dex",
        snapshot_date="2026-07-02",
        group_by="referrer_row__referrer",
    )
    assert {r["referrer_row__referrer"]: r["referrer_views_14d"] for r in rows(result)} == {
        "Google": 21,
        "gone.example": None,
    }
    result = query(
        project,
        "referrer_views_14d",
        "exmergo/dex",
        snapshot_date="2026-07-17",
        group_by="referrer_row__referrer",
    )
    assert all(r["referrer_views_14d"] is None for r in rows(result))
    # Monthly totals select the latest successful snapshot, including an empty one.
    result = dex(
        project,
        "explore",
        "semantic",
        "query",
        "referrer_views_14d",
        "--group-by",
        "metric_time,repository__name",
        "--grain",
        "month",
        "--local",
    )
    assert all(r["referrer_views_14d"] is None for r in rows(result))


def test_filtered_item_does_not_resurrect_old_snapshot(project):
    result = dex(
        project,
        "explore",
        "semantic",
        "query",
        "referrer_views_14d",
        "--local",
        "--where",
        "{{ Dimension('repository__name') }} = 'exmergo/dex' AND {{ Dimension('referrer_row__referrer') }} = 'gone.example' AND {{ TimeDimension('metric_time', 'day') }} < '2026-07-03'",
    )
    assert result_values(result)["referrer_views_14d"] is None


def test_all_metrics_are_executable(project):
    import json

    checked = json.loads((project / ".data/check.json").read_text())
    assert set(checked["metrics"]) == set(METRICS)
    assert checked["maintenance"]["check"]["data"]["axes_run"] == [
        "grain",
        "schema",
        "semantic",
        "volume",
    ]


def test_period_and_event_questions(project):
    result = answer(project, "growth", "exmergo/dex", end="2026-07-29", days=7)
    assert result["available"]
    assert result["changes"] == {
        "views": {"absolute": 0, "percent": 0},
        "clones": {"absolute": 0, "percent": 0},
    }
    event = answer(project, "event-impact", "exmergo/dex", event_id="exmergo/dex:release:1000")
    assert event["available"]
    assert event["coverage"][0]["end_exclusive"] == "2026-07-20"
    assert event["coverage"][1]["start"] == "2026-07-21"
    assert event["overlapping_events"]
    pending = answer(project, "traffic", "exmergo/dex", start="2026-06-29", end="2026-07-06")
    assert not pending["available"]
    assert pending["coverage"][0]["missing_dates"] == [date(2026, 6, 29), date(2026, 6, 30)]


def test_every_recipe(project):
    from oss_analytics.questions import RECIPES

    for name in RECIPES:
        options = {
            "snapshot_date": "2026-07-02",
            "compare_date": "2026-07-16",
            "event_id": "exmergo/dex:release:1000",
        }
        result = answer(project, name, "exmergo/dex", **options)
        assert result["available"] is (name != "active-users"), name
    missing = answer(project, "referrers", "exmergo/dex", snapshot_date="2026-07-03")
    assert not missing["available"]
    overlapping = answer(
        project,
        "referrer-change",
        "exmergo/dex",
        snapshot_date="2026-07-01",
        compare_date="2026-07-02",
    )
    assert overlapping["windows_overlap"]
    separate = answer(
        project,
        "referrer-change",
        "exmergo/dex",
        snapshot_date="2026-07-01",
        compare_date="2026-07-16",
    )
    assert not separate["windows_overlap"]


def test_zero_denominator_and_missing_day(workspace):
    with duckdb.connect(str(workspace / "warehouse/analytics.duckdb")) as c:
        c.execute(
            "update fct_traffic set views_total=0, views_unique=0 where repository='exmergo/dex' and date='2026-07-01'"
        )
        c.execute("delete from fct_traffic where repository='exmergo/dex' and date='2026-07-02'")
    assert (
        result_values(
            query(
                workspace,
                "views_per_visitor_day",
                "exmergo/dex",
                start="2026-07-01",
                end="2026-07-02",
            )
        )["views_per_visitor_day"]
        is None
    )
    report = coverage(workspace, "exmergo/dex", date(2026, 7, 1), date(2026, 7, 4))
    assert report["missing_dates"] == [date(2026, 7, 2)]
    assert not report["complete"]

"""Quarantine must survive the real Dex/MetricFlow build, check, and publication lifecycle."""

import pytest

from oss_analytics.io import read_json
from oss_analytics.lifecycle import build, check, publish
from oss_analytics.questions import answer, query, rows
from oss_analytics.status import status


@pytest.mark.parametrize(
    "endpoint,kind,field", [("referrers", "referrer", "referrer"), ("paths", "path", "url_path")]
)
def test_quarantined_snapshot_blocks_fallback_and_recovers(
    workspace, tmp_path, endpoint, kind, field
):
    manifest = read_json(workspace / ".data/sync.json")
    folder = workspace / manifest["directory"] / "exmergo/dex/ghrs-data/snapshots"
    body = f"{field},views_total,views_unique\nGoogle,10,5\nbad.example,2,3\n"
    # A later capture on the same day must suppress the earlier valid one.
    (folder / f"2026-07-02_052500_top_{endpoint}_snapshot.csv").write_text(body)
    bad = folder / f"2026-07-18_052500_top_{endpoint}_snapshot.csv"
    bad.write_text(body)
    built = build(workspace)
    checked = check(workspace)  # Compare against the existing baseline, never rebaseline.
    assert built["build"]["data"]["verification"]["ran"] is True
    assert set(checked["maintenance"]["check"]["data"]["axes_run"]) == {
        "schema",
        "volume",
        "grain",
        "semantic",
    }
    evidence = status(workspace)
    assert evidence["ready"]
    assert len(evidence["quarantined_snapshots"]) == 2
    repo = next(r for r in evidence["repositories"] if r["repository"] == "exmergo/dex")
    assert repo["latest_snapshot_availability"][endpoint] is False
    for day in ["2026-07-02", "2026-07-18"]:
        result = answer(workspace, endpoint, "exmergo/dex", snapshot_date=day)
        assert result["available"] is False
        assert "Quarantined" in result["reason"]
        result = query(
            workspace,
            f"{kind}_views_14d",
            "exmergo/dex",
            snapshot_date=day,
            group_by=f"{kind}_row__{kind}",
        )
        assert rows(result)
        assert all(r[f"{kind}_views_14d"] is None for r in rows(result))
    comparison = answer(
        workspace,
        f"{kind}-change",
        "exmergo/dex",
        snapshot_date="2026-07-16",
        compare_date="2026-07-18",
    )
    assert comparison["available"] is False
    # A real successful empty report remains available, distinct from quarantine.
    empty = answer(workspace, endpoint, "exmergo/dex", snapshot_date="2026-07-17")
    assert empty["available"] is True
    assert empty["snapshots"][0]["reported_item_count"] == 0
    assert answer(workspace, endpoint, "example/other", snapshot_date="2026-07-02")["available"]
    other_endpoint = "paths" if endpoint == "referrers" else "referrers"
    assert answer(workspace, other_endpoint, "exmergo/dex", snapshot_date="2026-07-02")["available"]
    assert (
        rows(query(workspace, "views", "exmergo/dex", start="2026-07-01", end="2026-07-03"))[0][
            "views"
        ]
        == 20
    )
    monthly = query(
        workspace, f"{kind}_views_14d", "exmergo/dex", group_by="metric_time", grain="month"
    )
    assert all(r[f"{kind}_views_14d"] is None for r in rows(monthly))
    if endpoint == "referrers":
        trend = answer(
            workspace, "referrer-trend", "exmergo/dex", start="2026-07-16", end="2026-07-19"
        )
        assert trend["windows"][0]["available"] is False
        assert all(v is None for v in trend["windows"][0]["views_14d"].values())
    publication = publish(workspace, tmp_path / "published", "a" * 40, "b" * 40)
    assert publication["quarantined_snapshots"] == evidence["quarantined_snapshots"]
    assert any("quarantined" in warning for warning in publication["warnings"])
    assert bad.read_text() == body
    # A newer valid capture restores availability without erasing the old anomaly.
    (folder / f"2026-07-18_062500_top_{endpoint}_snapshot.csv").write_text(
        f"{field},views_total,views_unique\nGoogle,12,6\n"
    )
    build(workspace)
    check(workspace)
    recovered = answer(workspace, endpoint, "exmergo/dex", snapshot_date="2026-07-18")
    assert recovered["available"] is True
    assert recovered["snapshots"][0]["rankings"]["Google"]["views"] == 12
    assert len(recovered["evidence"]["quarantined_snapshots"]) == 2
    repo = next(r for r in status(workspace)["repositories"] if r["repository"] == "exmergo/dex")
    assert repo["latest_snapshot_availability"][endpoint] is True

import hashlib
from datetime import datetime, timezone

import pytest

from oss_analytics.io import read_json
from oss_analytics.lifecycle import (
    ValidationError,
    assert_findings,
    build,
    check,
    publish,
    require_verified_build,
)
from oss_analytics.questions import answer
from oss_analytics.status import status


def test_failed_build_retains_database_and_previous_checks(workspace):
    db = workspace / "warehouse/analytics.duckdb"
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    manifest = read_json(workspace / ".data/sync.json")
    path = workspace / manifest["directory"] / "exmergo/dex/ghrs-data/views_clones_aggregate.csv"
    path.write_text("broken\n")
    with pytest.raises(ValueError):
        build(workspace)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert read_json(workspace / ".data/build.json")["validated"]


def test_unreviewed_definition_changes_block_answers_and_publication(workspace):
    model = workspace / "models/marts/fct_traffic.sql"
    model.write_text(model.read_text() + "\n-- a changed definition\n")
    assert not status(workspace)["ready"]
    with pytest.raises(ValidationError, match="changed"):
        answer(workspace, "traffic", "exmergo/dex")
    with pytest.raises(ValidationError, match="current build"):
        publish(workspace, workspace / ".data-branch", "a" * 40, "b" * 40)


def test_publication_manifest_and_state(project, tmp_path):
    result = publish(project, tmp_path, "a" * 40, "b" * 40)
    assert result["data_commit"] == "a" * 40
    assert result["lockfile"] == "uv.lock"
    assert result["lock_sha256"] == hashlib.sha256((project / "uv.lock").read_bytes()).hexdigest()
    assert (tmp_path / "analytics-state/snapshot.json").exists()
    assert read_json(tmp_path / "published.json") == result


def test_dependency_lock_change_invalidates_answers_and_publication(workspace):
    lock = workspace / "uv.lock"
    lock.write_text(lock.read_text() + "\n# dependency resolution changed\n")
    assert not status(workspace)["ready"]
    with pytest.raises(ValidationError, match="changed"):
        answer(workspace, "traffic", "exmergo/dex")
    with pytest.raises(ValidationError, match="current build"):
        publish(workspace, workspace / ".data-branch", "a" * 40, "b" * 40)


def test_maintenance_surfaces_structural_and_semantic_drift(workspace):
    # Change a measure definition without touching its source relation.
    semantic = workspace / "models/semantic.yml"
    text = semantic.read_text()
    semantic.write_text(text.replace("expr: views_total", "expr: clones_total", 1))
    # Dex reads the compiled semantic artifact, so rebuild first as an engineer would.
    build(workspace)
    with pytest.raises(ValidationError, match="blocking findings"):
        check(workspace)


def test_dex_findings_and_skips_cannot_pass_silently():
    result = {
        "data": {"verification": {"findings": [{"severity": "high", "code": "grain_broken"}]}}
    }
    with pytest.raises(ValidationError):
        assert_findings(result)
    volume = {"data": {"findings": [{"severity": "high", "axis": "volume"}]}}
    assert_findings(volume, structural_only=True)


@pytest.mark.parametrize("verification", [None, {}, {"ran": False}])
def test_unverified_dex_build_is_rejected(verification):
    data = {} if verification is None else {"verification": verification}
    with pytest.raises(ValidationError, match="verification did not run"):
        require_verified_build({"status": "ok", "data": data})


def test_status_distinguishes_freshness_from_coverage(project):
    result = status(project, at=datetime(2026, 9, 1, tzinfo=timezone.utc))
    dex = next(r for r in result["repositories"] if r["repository"] == "exmergo/dex")
    assert dex["freshness"] == "critical"
    assert dex["last_traffic_date"].isoformat() == "2026-08-29"
    assert dex["traffic_lag_days"] == 3
    assert result["ready"]


def test_first_capture_missing_legacy_series_and_optional_urls(workspace):
    from oss_analytics.lifecycle import baseline

    manifest = read_json(workspace / ".data/sync.json")
    for index, source in enumerate(manifest["sources"]):
        folder = workspace / manifest["directory"] / source["repository"]
        (folder / "ghrs-data/forks.csv").unlink()
        # A new project: nothing closed or merged yet.
        (folder / "signals/issues.csv").write_text(
            "number,kind,created_at,closed_at,merged_at,author_association\n"
            "1,issue,2026-07-01T10:00:00Z,,,NONE\n"
            "2,pull_request,2026-07-02T00:00:00Z,,,NONE\n"
        )
        for path in (folder / "metadata").glob("*.json"):
            if index == 0 and path.name == "1.json":
                value = read_json(path)
                value["releases"] = []
                path.write_text(__import__("json").dumps(value))
            else:
                path.unlink()
    (workspace / "seeds/annotations.csv").write_text(
        "event_id,repository,event_date,kind,title,url\n"
        "launch,exmergo/dex,2026-07-21,campaign,Launch post,\n"
    )
    build(workspace)
    baseline(workspace)
    report = check(workspace)
    expected = report["expected_nullable_fields"]
    assert "main.fct_observations.stars_net_change" in expected
    assert "main.fct_legacy.forks" in expected
    assert "main.annotations.url" in expected
    assert "main.dim_event.url" in expected
    assert "raw.issues.closed_at" in expected
    assert "raw.issues.merged_at" in expected
    result = answer(workspace, "star-growth", "exmergo/dex")
    assert not result["available"]
    assert result["reason"]


def test_actual_grain_regression_blocks_and_invalidates_readiness(workspace):
    import duckdb

    with duckdb.connect(str(workspace / "warehouse/analytics.duckdb")) as connection:
        connection.execute("insert into fct_traffic select * from fct_traffic limit 1")
    with pytest.raises(ValidationError, match="blocking findings"):
        check(workspace)
    assert not status(workspace)["ready"]


def test_tutorial_plan_apply_and_semantic_query(workspace):
    import shutil
    import subprocess
    import sys
    from pathlib import Path
    from oss_analytics.lifecycle import baseline, dex

    script = Path(__file__).resolve().parents[1] / "scripts/prepare_lifecycle_example.py"
    (workspace / "scripts").mkdir()
    shutil.copy2(script, workspace / "scripts" / script.name)
    subprocess.run([sys.executable, str(workspace / "scripts" / script.name)], check=True)
    planned = dex(
        workspace,
        "transform",
        "plan",
        "Expose observed days with views",
        "--edits-file",
        str(workspace / ".data/tutorial-edits.json"),
    )
    dex(workspace, "transform", "apply", planned["data"]["plan_id"])
    assert "has_page_views" in (workspace / "models/marts/fct_traffic.sql").read_text()
    build(workspace)
    result = dex(
        workspace,
        "explore",
        "semantic",
        "query",
        "views",
        "--local",
        "--group-by",
        "repository__name,traffic_row__has_page_views",
    )
    data = result["data"]
    rows = [dict(zip(data["columns"], row)) for row in data["cells"]]
    assert {r["repository__name"]: r["views"] for r in rows} == {
        "exmergo/dex": 600,
        "example/other": 660,
    }
    drift = dex(workspace, "maintain", "semantic")
    assert any(f["code"] == "definition_changed" for f in drift["data"]["findings"])
    baseline(workspace)
    accepted = dex(workspace, "maintain", "semantic")
    assert not any(f["code"] == "definition_changed" for f in accepted["data"]["findings"])


def test_capture_days_stay_utc_under_local_timezone(workspace):
    import json
    import duckdb
    import yaml

    manifest = read_json(workspace / ".data/sync.json")
    folder = workspace / manifest["directory"] / "exmergo/dex"
    for name, captured_at in [
        ("1.json", "2026-07-01T23:55:00Z"),
        ("2.json", "2026-07-02T00:05:00Z"),
    ]:
        path = folder / "metadata" / name
        observation = read_json(path)
        observation["captured_at"] = captured_at
        path.write_text(json.dumps(observation))
    for endpoint in ["paths", "referrers"]:
        original = folder / "ghrs-data/snapshots" / f"2026-07-01_042500_top_{endpoint}_snapshot.csv"
        original.rename(original.with_name(f"2026-07-01_235500_top_{endpoint}_snapshot.csv"))
    profiles = yaml.safe_load((workspace / "profiles.yml").read_text())
    profiles["oss_analytics"]["outputs"]["dev"]["settings"]["TimeZone"] = "Europe/Rome"
    (workspace / "profiles.yml").write_text(yaml.safe_dump(profiles))
    build(workspace)
    with duckdb.connect(str(workspace / "warehouse/analytics.duckdb"), read_only=True) as c:
        observed = c.execute(
            "select date, stars, stars_net_change from fct_observations where repository='exmergo/dex' order by date"
        ).fetchall()
        snapshots = c.execute(
            "select date from fct_snapshot_status where repository='exmergo/dex' and endpoint='paths' order by date"
        ).fetchall()
    assert str(observed[0][0]) == "2026-07-01"
    assert observed[0][1] == 10
    assert str(observed[1][0]) == "2026-07-02"
    assert observed[1][2] == -2
    assert str(snapshots[0][0]) == "2026-07-01"

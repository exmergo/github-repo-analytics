"""Deployment collection contracts and governed MetricFlow values."""

import json
from copy import deepcopy

import pytest

from oss_analytics.config import Source, load_sources
from oss_analytics.deployments import collect_deployments
from oss_analytics.io import SourceError, read_json
from oss_analytics.questions import query, result_values
from oss_analytics.sources import collect_signals
from oss_analytics.warehouse import SCHEMAS, parse_deployments

A, B, C = (c * 40 for c in "abc")
SOURCE = Source("exmergo/dex", deployments={"source": "github", "environment": "prod / live"})


class DeploymentClient:
    def __init__(self):
        self.routes = []
        self.complete = True
        self.fail = False
        self.deployments = [
            {"id": 1, "environment": "prod / live", "sha": A},
            {"id": 2, "environment": "prod / live", "sha": B},
            {"id": 3, "environment": "preview", "sha": A},
            {"id": 4, "environment": "prod / live", "sha": A, "transient_environment": True},
            {"id": 5, "environment": "prod / live", "sha": A},
        ]
        self.statuses = {
            1: [
                self.status("inactive", "2026-07-05T00:00:00Z"),
                self.status("success", "2026-07-03T12:00:00Z"),
                self.status("success", "2026-07-03T13:00:00Z"),
            ],
            2: [self.status("success", "2026-07-04T12:00:00Z")],
            5: [self.status("failure", "2026-07-02T00:00:00Z")],
        }
        self.pulls = [
            self.pull(10, C),
            self.pull(11, A),
            self.pull(12, C, merged_at=None),
            self.pull(13, C, branch="release"),
            self.pull(14, C, merged_at="2026-07-05T00:00:00Z"),
        ]
        self.comparisons = {(C, A): "ahead", (C, B): "diverged", (A, B): "behind"}

    @staticmethod
    def status(state, when):
        return {"state": state, "created_at": when, "environment": "prod / live"}

    @staticmethod
    def pull(number, sha, merged_at="2026-07-03T08:00:00Z", branch="main"):
        return {
            "number": number,
            "merge_commit_sha": sha,
            "merged_at": merged_at,
            "base": {"ref": branch},
            "user": {"login": "never-store-this"},
            "title": "do not store",
        }

    def json(self, route):
        self.routes.append(route)
        if self.fail:
            raise SourceError("API unavailable")
        if "/compare/" in route:
            pair = tuple(route.split("/compare/")[1].split("..."))
            return {"status": self.comparisons[pair]}
        assert route == "/repos/exmergo/dex"
        return {"default_branch": "main"}

    def paginate(self, route, **kwargs):
        self.routes.append(route)
        if "/statuses?" in route:
            return self.statuses[int(route.split("/")[-2])], self.complete
        if "/deployments?" in route:
            if self.deployments:
                assert "environment=prod%20%2F%20live" in route
            return self.deployments, self.complete
        if "/pulls?" in route:
            assert "base=main" in route
            return self.pulls, self.complete
        if "/stargazers?" in route or "/forks?" in route or "/issues?" in route:
            return [], True
        raise AssertionError(route)


def test_success_environment_ancestry_and_repeat_collection(tmp_path):
    client = DeploymentClient()
    path = tmp_path / "deployments.json"
    result = collect_deployments(client, SOURCE, path)
    body = read_json(path)
    assert result["complete"] and result["items"] == 2
    assert [r["deployment_id"] for r in body["deployments"]] == [1, 2]
    assert body["deployments"][0]["succeeded_at"] == "2026-07-03T12:00:00Z"
    assert [(r["deployment_id"], r["number"]) for r in body["changes"]] == [(1, 10), (1, 11)]
    assert "never-store-this" not in path.read_text() and "do not store" not in path.read_text()
    before = path.read_bytes()
    collect_deployments(client, SOURCE, path)
    assert path.read_bytes() == before
    # A SHA identical to a deployment is contained without a compare API call.
    assert not any("/compare/" + A + "..." + A in r for r in client.routes)
    # GitHub can remove historical success statuses; retained evidence survives.
    client.statuses[1] = [client.status("inactive", "2026-07-05T00:00:00Z")]
    collect_deployments(client, SOURCE, path)
    assert path.read_bytes() == before
    client.fail = True
    with pytest.raises(SourceError):
        collect_deployments(client, SOURCE, path)
    assert path.read_bytes() == before


def test_completeness_and_environment_change(tmp_path):
    client = DeploymentClient()
    client.complete = False
    path = tmp_path / "deployments.json"
    assert collect_deployments(client, SOURCE, path)["complete"] is False
    client.complete = True
    # Old environment evidence is never attributed to the newly configured environment.
    source = Source("exmergo/dex", deployments={"source": "github", "environment": "production"})
    client.deployments = []
    client.pulls = []
    collect_deployments(client, source, path)
    assert read_json(path)["deployments"] == []
    assert read_json(path)["changes"] == []


def test_disabled_and_failed_signal_preserves_capture(tmp_path):
    client = DeploymentClient()
    old = "2026-07-06T00:00:00+00:00"
    collect_signals(client, Source("exmergo/dex"), tmp_path, old)
    assert not any("/deployments?" in r for r in client.routes)
    first = collect_signals(client, SOURCE, tmp_path, old)
    assert first["deployments"]["captured_at"] == old
    before = (tmp_path / "exmergo/dex/signals/deployments.json").read_bytes()
    client.fail = True
    result = collect_signals(client, SOURCE, tmp_path, "2026-07-07T00:00:00+00:00")
    assert result["deployments"]["captured_at"] == old
    assert any("deployments: API unavailable" in r for r in result["errors"])
    assert (tmp_path / "exmergo/dex/signals/deployments.json").read_bytes() == before


@pytest.mark.parametrize(
    "settings",
    [
        "true",
        "{source: github}",
        "{source: workflow, environment: production}",
        "{source: releases, environment: production}",
        "{source: github, environment: ''}",
        "{source: github, environment: 123}",
        "{source: github, environment: prod, branch: main}",
    ],
)
def test_invalid_deployment_settings(tmp_path, settings):
    (tmp_path / "sources.yml").write_text(
        f"repositories:\n  - repository: exmergo/dex\n    deployments: {settings}\n"
    )
    with pytest.raises(ValueError, match="deployments"):
        load_sources(tmp_path)


def test_parser_rejects_duplicate_or_orphan_and_negative_evidence(tmp_path):
    path = tmp_path / "deployments.json"
    client = DeploymentClient()
    capture = collect_deployments(client, SOURCE, path)
    body = read_json(path)
    tables = {n: [] for n in SCHEMAS}
    parse_deployments(SOURCE.repository, path, tables, capture)
    assert len(tables["deployments"]) == 2 and len(tables["deployment_changes"]) == 2
    for defect in ["duplicate", "orphan", "negative", "sha", "environment"]:
        broken = deepcopy(body)
        if defect == "duplicate":
            broken["changes"].append(broken["changes"][0])
        elif defect == "orphan":
            broken["changes"][0]["deployment_id"] = 999
        elif defect == "negative":
            broken["changes"][0]["merged_at"] = "2026-07-10T00:00:00Z"
        elif defect == "sha":
            broken["deployments"][0]["sha"] = "main"
        else:
            broken["environment"] = "preview"
        path.write_text(json.dumps(broken))
        with pytest.raises(ValueError):
            parse_deployments(SOURCE.repository, path, {n: [] for n in SCHEMAS}, capture)


def test_metricflow_frequency_and_pr_weighted_median(project):
    values = result_values(
        query(
            project,
            "deployments,median_hours_lead_time",
            "exmergo/dex",
            start="2026-07-01",
            end="2026-07-07",
        )
    )
    assert values == {"deployments": 4, "median_hours_lead_time": 4.0}
    # Two PRs in the first deployment still count as one deployment; continuous median 3h.
    assert result_values(
        query(
            project,
            "deployments,median_hours_lead_time",
            "exmergo/dex",
            start="2026-07-03",
            end="2026-07-04",
        )
    ) == {"deployments": 1, "median_hours_lead_time": 3.0}
    # Redeployment counts, but cannot ship either PR again.
    redeploy = result_values(
        query(
            project,
            "deployments,median_hours_lead_time",
            "exmergo/dex",
            start="2026-07-04",
            end="2026-07-05",
        )
    )
    assert redeploy == {"deployments": 1, "median_hours_lead_time": None}
    # Repository/PR and deployment IDs intentionally collide across projects.
    assert result_values(query(project, "median_hours_lead_time", "example/other")) == {
        "median_hours_lead_time": 48.0
    }
    # Capture UTC day is incomplete, so neither the count nor median reports activity.
    partial = query(
        project,
        "deployments,median_hours_lead_time",
        "exmergo/dex",
        start="2026-08-31",
        end="2026-09-01",
    )
    assert not partial["data"]["cells"] or all(
        v is None for r in partial["data"]["cells"] for v in r
    )


def test_deployment_recipe_preserves_period_and_missing_medians(project):
    from oss_analytics.questions import answer

    response = answer(
        project, "deployments", "exmergo/dex", start="2026-07-01", end="2026-07-07", grain="day"
    )
    assert response["available"] and not response["zero_when_null"]
    assert str(response["period"]["end_exclusive"]) == "2026-07-07"
    assert response["units"]["median_hours_lead_time"] == "hours"
    partial = answer(project, "deployments", "exmergo/dex", start="2026-08-30", end="2026-09-01")
    assert not partial["available"] and "partial capture day" in partial["reason"]


def test_missing_and_incomplete_recipe_does_not_query_or_impute():
    from oss_analytics.questions import deployment_answer
    from datetime import datetime, timezone

    absent = deployment_answer(None, {}, "a/b", {"signals": {}}, None, None, 7, "week")
    assert not absent["available"] and "No deployment capture" in absent["reason"]
    record = {
        "signals": {
            "deployments": {
                "complete": False,
                "captured_at": datetime(2026, 7, 7, tzinfo=timezone.utc),
            }
        }
    }
    truncated = deployment_answer(None, {}, "a/b", record, None, None, 7, "week")
    assert not truncated["available"] and "incomplete" in truncated["reason"]


def test_ancestry_limit_preserves_the_entire_previous_capture(tmp_path):
    client = DeploymentClient()
    path = tmp_path / "deployments.json"
    collect_deployments(client, SOURCE, path)
    before = path.read_bytes()
    client.pulls = [client.pull(1000 + i, f"{i:040x}") for i in range(1001)]
    client.comparisons = {(f"{i:040x}", A): "ahead" for i in range(1001)}
    with pytest.raises(SourceError, match="1000 comparisons"):
        collect_deployments(client, SOURCE, path)
    assert path.read_bytes() == before


def test_compare_failure_does_not_publish_partial_new_successes(tmp_path):
    client = DeploymentClient()
    path = tmp_path / "deployments.json"
    collect_deployments(client, SOURCE, path)
    before = path.read_bytes()
    client.pulls.append(client.pull(99, "d" * 40))
    original = client.json

    def fail_compare(route):
        if "/compare/" + "d" * 40 in route:
            raise SourceError("compare permission denied")
        return original(route)

    client.json = fail_compare
    with pytest.raises(SourceError, match="compare permission denied"):
        collect_deployments(client, SOURCE, path)
    assert path.read_bytes() == before

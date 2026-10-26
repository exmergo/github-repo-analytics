"""Collect deployment and commit-containment evidence; dbt owns lead-time attribution."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from .config import REVISION, Source
from .io import SourceError, read_json, write_json
from .warehouse import timestamp


def collect_deployments(client, source: Source, path: Path) -> dict:
    repository = source.repository
    environment = source.deployments["environment"]
    branch = client.json(f"/repos/{repository}")["default_branch"]
    previous = read_json(path, {})
    if previous.get("environment") != environment or previous.get("default_branch") != branch:
        previous = {}
    # Retain previously observed successes even when GitHub ages out old statuses.
    deployments = {r["deployment_id"]: r for r in previous.get("deployments", [])}
    changes = {(r["deployment_id"], r["number"]): r for r in previous.get("changes", [])}
    rows, complete = client.paginate(
        f"/repos/{repository}/deployments?environment={quote(environment, safe='')}&per_page=100",
        max_pages=50,
    )
    for row in rows:
        if row["environment"] != environment or row.get("transient_environment", False):
            continue
        sha = row["sha"].lower()
        if not REVISION.fullmatch(sha):
            raise SourceError("deployment has no immutable commit SHA")
        statuses, all_statuses = client.paginate(
            f"/repos/{repository}/deployments/{row['id']}/statuses?per_page=100", max_pages=50
        )
        complete = complete and all_statuses
        successes = [
            s
            for s in statuses
            if s["state"] == "success" and s.get("environment", environment) == environment
        ]
        if not successes:
            continue
        succeeded_at = min((s["created_at"] for s in successes), key=timestamp)
        old = deployments.get(row["id"])
        if old and timestamp(old["succeeded_at"]) < timestamp(succeeded_at):
            succeeded_at = old["succeeded_at"]
        deployments[row["id"]] = {
            "deployment_id": row["id"],
            "environment": environment,
            "sha": sha,
            "succeeded_at": succeeded_at,
        }
    pulls, all_pulls = client.paginate(
        f"/repos/{repository}/pulls?state=closed&base={quote(branch, safe='')}&per_page=100",
        max_pages=50,
    )
    complete = complete and all_pulls
    comparisons = {}
    for pull in pulls:
        if not pull.get("merged_at") or pull["base"]["ref"] != branch:
            continue
        merge_sha = (pull.get("merge_commit_sha") or "").lower()
        if not REVISION.fullmatch(merge_sha):
            complete = False
            continue
        for deployment in sorted(
            deployments.values(),
            key=lambda r: (timestamp(r["succeeded_at"]), r["deployment_id"]),
        ):
            if timestamp(deployment["succeeded_at"]) < timestamp(pull["merged_at"]):
                continue
            pair = (deployment["deployment_id"], pull["number"])
            if pair in changes:
                break
            comparison = (merge_sha, deployment["sha"])
            if comparison not in comparisons:
                if len(comparisons) >= 1000:
                    raise SourceError(
                        "deployment ancestry exceeds 1000 comparisons; previous evidence retained"
                    )
                if merge_sha == deployment["sha"]:
                    comparisons[comparison] = True
                else:
                    result = client.json(
                        f"/repos/{repository}/compare/{merge_sha}...{deployment['sha']}"
                    )
                    comparisons[comparison] = result["status"] in {"ahead", "identical"}
            if comparisons[comparison]:
                changes[pair] = {
                    "deployment_id": deployment["deployment_id"],
                    "number": pull["number"],
                    "merged_at": pull["merged_at"],
                    "merge_sha": merge_sha,
                }
                break
    # One atomic file: an API failure cannot publish half a new attribution dataset.
    write_json(
        path,
        {
            "environment": environment,
            "default_branch": branch,
            "deployments": sorted(deployments.values(), key=lambda r: r["deployment_id"]),
            "changes": sorted(changes.values(), key=lambda r: (r["deployment_id"], r["number"])),
        },
    )
    return {
        "complete": complete,
        "environment": environment,
        "default_branch": branch,
        "items": len(deployments),
        "mapped_pairs": len(changes),
    }

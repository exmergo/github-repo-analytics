"""Run Dex's actual lifecycle and inspect its structured results."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .io import publication_provenance, read_json, write_json
from .sources import now_iso
from .warehouse import load


class ValidationError(RuntimeError):
    pass


def dex(root: Path, *arguments: str, database: Path | None = None) -> dict:
    args = [sys.executable, "-m", "exmergo_dex_core", *arguments]
    if database:
        args.extend(["--path", str(database)])
    env = os.environ.copy()
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    env["DBT_PROFILES_DIR"] = str(root)
    env["DBT_SEND_ANONYMOUS_USAGE_STATS"] = "false"
    if database:
        env["OSS_ANALYTICS_WAREHOUSE"] = str(database)
    process = subprocess.run(args, cwd=root, env=env, capture_output=True, text=True)
    try:
        result = json.loads(process.stdout)
    except ValueError:
        raise ValidationError(
            "Dex did not return a JSON envelope: " + process.stderr[-2000:]
        ) from None
    if process.returncode or result.get("status") != "ok":
        raise ValidationError(json.dumps(result, default=str))
    return result


def findings(result: dict) -> list[dict]:
    """Dex nests findings by axis; inspect all of them, including verification."""
    found = {}

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "findings" and isinstance(child, list):
                    # Maintain lists each finding both in total and under its axis.
                    for x in child:
                        if isinstance(x, dict):
                            found.setdefault(json.dumps(x, sort_keys=True, default=str), x)
                else:
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(result.get("data", {}))
    return list(found.values())


def assert_findings(result: dict, *, structural_only=False, expected_nulls=None):
    bad = []
    for finding in findings(result):
        relation = ".".join((finding.get("identifier") or "").split(".")[-2:])
        field = relation + "." + (finding.get("column") or "")
        if finding.get("code") == "fully_null_column" and field in (expected_nulls or {}):
            continue
        # Expected row-volume changes do not authorize redefining the data model.
        text = json.dumps(finding).lower()
        volume = '"axis": "volume"' in text or '"kind": "volume' in text
        changed_definition = finding.get("axis") == "semantic" and finding.get(
            "code", ""
        ).startswith("definition_")
        if changed_definition or (
            finding.get("severity") in {"high", "critical", "error"}
            and not (structural_only and volume)
        ):
            bad.append(finding)
    if bad:
        message = "Dex reported blocking findings: " + json.dumps(bad)
        if all(
            f.get("axis") == "semantic" and f.get("code", "").startswith("definition_") for f in bad
        ):
            # A merged definition change needs an explicit acceptance, never an automatic one.
            message += (
                ". Metric definitions differ from the accepted baseline. If they match a"
                " reviewed change, accept it with `oss-analytics baseline` (CI: dispatch"
                " with accept_baseline=true); see docs/operations.md#accepting-a-reviewed-change"
            )
        raise ValidationError(message)


def require_verified_build(result: dict):
    """An absent or skipped verification is not evidence for publishing a build."""
    if result.get("data", {}).get("verification", {}).get("ran") is not True:
        raise ValidationError("Dex build verification did not run")
    assert_findings(result)


def build(root: Path) -> dict:
    manifest = read_json(root / ".data/sync.json")
    if not manifest:
        raise ValidationError("run oss-analytics sync before build")
    import uuid

    work = root / ".data/workspaces" / uuid.uuid4().hex
    work.mkdir(parents=True)
    candidate = work / "warehouse/analytics.duckdb"
    state_files = [
        root / ".dex/cache.json",
        root / "target/manifest.json",
        root / "target/semantic_manifest.json",
        root / "target/run_results.json",
    ]
    previous = {p: p.read_bytes() if p.exists() else None for p in state_files}
    try:
        for name in ["dbt_project.yml", "profiles.yml"]:
            shutil.copy2(root / name, work / name)
        for folder in ["models", "seeds", "data_tests"]:
            if (root / folder).exists():
                shutil.copytree(root / folder, work / folder)
        (work / ".dex").mkdir()
        shutil.copy2(root / ".dex/config.yml", work / ".dex/config.yml")
        warnings = load(root, manifest, candidate)
        result = dex(work, "transform", "build", "--target", "dev", "--verify")
        require_verified_build(result)
        dex(work, "explore", "map", "--use-project", "--verify")
        smoke_metrics(work)
        for path in state_files:
            source = work / path.relative_to(root)
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, path)
        final = root / "warehouse/analytics.duckdb"
        final.parent.mkdir(parents=True, exist_ok=True)
        os.replace(candidate, final)
        record = {
            "built_at": now_iso(),
            "code_digest": code_digest(root),
            "inputs": manifest,
            "warnings": warnings,
            "build": result,
            "validated": False,
        }
        write_json(root / ".data/build.json", record)
        return record
    except Exception:
        # The previous database is replaced only after all candidate checks succeed.
        for path, content in previous.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        raise
    finally:
        shutil.rmtree(work)


def smoke_metrics(root: Path, *, database=None) -> list[str]:
    from .questions import METRICS, TIME_METRICS

    tested = []
    for metric in METRICS:
        grouping = ["--group-by", "repository__name"]
        if metric in TIME_METRICS:
            grouping = [
                "--group-by",
                "repository__name,metric_time",
                "--grain",
                TIME_METRICS[metric],
            ]
        result = dex(
            root,
            "explore",
            "semantic",
            "query",
            metric,
            *grouping,
            "--local",
            database=database,
        )
        if result.get("data", {}).get("truncated"):
            raise ValidationError(f"semantic smoke query was truncated: {metric}")
        tested.append(metric)
    return tested


def check(root: Path) -> dict:
    built = read_json(root / ".data/build.json")
    if not built:
        raise ValidationError("build the dataset before checking it")
    if built.get("code_digest") != code_digest(root):
        raise ValidationError("definitions changed since the last build; rebuild before checking")
    if read_json(root / ".data/sync.json", {}).get("directory") != built["inputs"]["directory"]:
        raise ValidationError("new inputs have not been built; build before checking")
    built["validated"] = False
    write_json(root / ".data/build.json", built)
    if not (root / ".dex/snapshot.json").exists():
        raise ValidationError(
            "no maintenance baseline: run oss-analytics baseline after reviewing the build"
        )
    metrics = smoke_metrics(root)
    from .quality import expected_nullable_fields

    expected_nulls = expected_nullable_fields(root)
    results = {}
    for command in ["check", "verify"]:
        result = dex(root, "maintain", command)
        assert_findings(result, structural_only=True, expected_nulls=expected_nulls)
        if command == "check" and not {"schema", "volume", "grain", "semantic"}.issubset(
            result.get("data", {}).get("axes_run", [])
        ):
            raise ValidationError("Dex skipped one or more required maintenance axes")
        results[command] = result
    record = {
        "checked_at": now_iso(),
        "metrics": metrics,
        "maintenance": results,
        "expected_nullable_fields": expected_nulls,
        "input_directory": built["inputs"]["directory"],
        "code_digest": code_digest(root),
    }
    built["validated"] = True
    write_json(root / ".data/build.json", built)
    write_json(root / ".data/check.json", record)
    return record


def baseline(root: Path) -> dict:
    built = read_json(root / ".data/build.json")
    if not built:
        raise ValidationError("build before accepting a baseline")
    require_verified_build(built.get("build", {}))
    if built.get("code_digest") != code_digest(root):
        raise ValidationError("definitions changed since the last build; rebuild before baselining")
    if read_json(root / ".data/sync.json", {}).get("directory") != built["inputs"]["directory"]:
        raise ValidationError("new inputs have not been built; build before baselining")
    return dex(root, "maintain", "snapshot")


def code_digest(root: Path) -> str:
    digest = hashlib.sha256()
    paths = [
        root / n
        for n in [
            "pyproject.toml",
            "uv.lock",
            "sources.yml",
            "dbt_project.yml",
            "profiles.yml",
            ".dex/config.yml",
        ]
    ]
    for folder, pattern in [("models", "*"), ("seeds", "*"), ("data_tests", "*"), ("src", "*.py")]:
        paths.extend(
            p
            for p in (root / folder).rglob(pattern)
            if p.is_file() and "__pycache__" not in p.parts
        )
    for path in sorted(paths):
        if path.exists():
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def publish(root: Path, destination: Path, data_commit: str, code_commit: str) -> dict:
    from .config import REVISION

    if not REVISION.fullmatch(data_commit) or not REVISION.fullmatch(code_commit):
        raise ValueError("publication requires full data and code commit SHAs")
    built = read_json(root / ".data/build.json")
    checked = read_json(root / ".data/check.json")
    if (
        not built
        or not built.get("validated")
        or not checked
        or (
            checked["input_directory"] != built["inputs"]["directory"]
            or checked["code_digest"] != code_digest(root)
            or read_json(root / ".data/sync.json", {}).get("directory")
            != built["inputs"]["directory"]
        )
    ):
        raise ValidationError(
            "publication requires checks against the current build and definitions"
        )
    lock = root / "uv.lock"
    if not lock.exists():
        raise ValidationError("uv.lock is required for publication")
    record = {
        "version": 1,
        "data_commit": data_commit,
        "code_commit": code_commit,
        "lockfile": "uv.lock",
        "lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
        "validated_at": checked["checked_at"],
        # Older inputs may already embed a full prior publication. Compact here too,
        # so upgrading does not require re-importing or trusting those nested sources.
        "sources": [
            {**source, "publication": publication_provenance(source.get("publication"))}
            for source in built["inputs"]["sources"]
        ],
        "metrics_tested": checked["metrics"],
    }
    destination.mkdir(parents=True, exist_ok=True)
    state = destination / "analytics-state"
    state.mkdir(exist_ok=True)
    for name in ["cache.json", "snapshot.json"]:
        shutil.copy2(root / ".dex" / name, state / name)
    write_json(destination / "published.json", record)
    return record

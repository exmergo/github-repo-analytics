"""Explicitly opted-in network test. Normal PR checks are entirely deterministic."""

from pathlib import Path
import shutil
import pytest
from oss_analytics.sources import sync
from oss_analytics.lifecycle import build, baseline, check


def test_live_example(request, tmp_path):
    if not request.config.getoption("--live"):
        pytest.skip("use --live to enable public GitHub access")
    source = Path(__file__).resolve().parents[1]
    for name in [
        "sources.yml",
        "dbt_project.yml",
        "profiles.yml",
        "uv.lock",
        "pyproject.toml",
    ]:
        shutil.copy2(source / name, tmp_path / name)
    for name in ["models", "seeds", "data_tests"]:
        shutil.copytree(source / name, tmp_path / name)
    (tmp_path / ".dex").mkdir()
    shutil.copy2(source / ".dex/config.yml", tmp_path / ".dex/config.yml")
    manifest = sync(tmp_path)
    assert manifest["sources"][0]["repository"] == "exmergo/dex"
    build(tmp_path)
    baseline(tmp_path)
    assert check(tmp_path)["metrics"]

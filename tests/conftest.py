from pathlib import Path
import shutil
import pytest

from oss_analytics.lifecycle import baseline, build, check
from make_fixture import make_fixture

ROOT = Path(__file__).resolve().parents[1]


def pytest_addoption(parser):
    parser.addoption(
        "--live", action="store_true", default=False, help="enable external GitHub smoke"
    )


@pytest.fixture(scope="session")
def project(tmp_path_factory):
    root = tmp_path_factory.mktemp("analytics")
    for name in [
        "dbt_project.yml",
        "profiles.yml",
        "sources.yml",
        "pyproject.toml",
        "uv.lock",
    ]:
        shutil.copy2(ROOT / name, root / name)
    for name in ["models", "seeds", "data_tests"]:
        shutil.copytree(ROOT / name, root / name)
    (root / ".dex").mkdir()
    shutil.copy2(ROOT / ".dex/config.yml", root / ".dex/config.yml")
    make_fixture(root)
    (root / "seeds/annotations.csv").write_text(
        "event_id,repository,event_date,kind,title,url\n"
        "launch,exmergo/dex,2026-07-21,campaign,Launch post,https://example.com/launch\n"
    )
    build(root)
    baseline(root)
    check(root)
    return root


@pytest.fixture
def workspace(project, tmp_path):
    root = tmp_path / "analytics"
    shutil.copytree(project, root)
    return root

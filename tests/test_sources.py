import hashlib
import json
from unittest.mock import patch
import urllib.error

import pytest

from oss_analytics.config import load_sources
from oss_analytics.io import GitHub, SourceError, read_json
from oss_analytics.sources import import_source, sync
from oss_analytics.warehouse import parse_inputs
from make_fixture import make_fixture

SHA = "a" * 40


class FakeGitHub:
    def __init__(self, files, *, publication=None, truncated=False):
        self.files = files
        self.publication = publication
        self.truncated = truncated
        self.routes = []

    def json(self, route, **kwargs):
        self.routes.append(route)
        if "/commits/" in route:
            return {"sha": SHA}
        if "/git/trees/" in route:
            return {
                "truncated": self.truncated,
                "tree": [{"path": p, "type": "blob"} for p in self.files],
            }
        raise AssertionError(route)

    def get(self, url, **kwargs):
        if url.endswith("/published.json"):
            return json.dumps(self.publication).encode() if self.publication else None
        # Assert downloads are pinned, not made from a moving branch name.
        assert "/" + SHA + "/" in url or self.publication
        return self.files[url.split("/", 6)[6]]


def input_root(tmp_path):
    (tmp_path / "seeds").mkdir()
    (tmp_path / "seeds/annotations.csv").write_text(
        "event_id,repository,event_date,kind,title,url\n"
    )
    (tmp_path / "sources.yml").write_text("repositories:\n  - repository: exmergo/dex\n")
    return tmp_path


def upstream_files():
    return {
        "exmergo/dex/ghrs-data/views_clones_aggregate.csv": b"time_iso8601,clones_total,clones_unique,views_total,views_unique\n2026-07-01T00:00:00Z,0,0,0,0\n"
    }


def test_atomic_immutable_sync_and_repeat(tmp_path):
    root = input_root(tmp_path)
    client = FakeGitHub(upstream_files())
    first = sync(root, client=client, supplement=False)
    second = sync(root, client=client, supplement=False)
    assert first["directory"] != second["directory"]
    assert read_json(root / ".data/sync.json") == second
    tables, warnings = parse_inputs(root, second)
    assert len(tables["traffic"]) == 1
    assert tables["repositories"][0][1] == "name:exmergo/dex"
    assert tables["traffic"][0][2:] == (0, 0, 0, 0)
    assert (
        second["sources"][0]["files"]["exmergo/dex/ghrs-data/views_clones_aggregate.csv"]
        == hashlib.sha256(next(iter(upstream_files().values()))).hexdigest()
    )
    files = upstream_files()
    files["exmergo/dex/ghrs-data/views_clones_aggregate.csv"] = b"wrong,header\n"
    with pytest.raises(ValueError, match="columns"):
        sync(root, client=FakeGitHub(files), supplement=False)
    assert read_json(root / ".data/sync.json") == second


def test_truncated_tree_does_not_activate(tmp_path):
    root = input_root(tmp_path)
    with pytest.raises(SourceError, match="truncated"):
        sync(root, client=FakeGitHub(upstream_files(), truncated=True), supplement=False)
    assert not (root / ".data/sync.json").exists()


def test_published_source_defaults_to_approved_revision(tmp_path):
    root = input_root(tmp_path)
    source = load_sources(root)[0]
    approved = "b" * 40
    client = FakeGitHub(upstream_files(), publication={"data_commit": approved})
    result = import_source(root, source, root / ".data/input", client=client)
    assert result["source_revision"] == approved
    assert any(approved in r for r in client.routes)
    replay = import_source(root, source, root / ".data/replay", client=client, revision=SHA)
    assert replay["source_revision"] == SHA


@pytest.mark.parametrize(
    "body",
    [
        "repositories:\n  - repository: ../dex\n",
        "repositories:\n  - repository: exmergo/dex\n  - repository: Exmergo/Dex\n",
        "repositories:\n  - repository: exmergo/dex\n    mode: other\n",
        "repositories:\n  - repository: exmergo/dex\n    expected_refresh_hours: 0\n",
    ],
)
def test_invalid_config(tmp_path, body):
    (tmp_path / "sources.yml").write_text(body)
    with pytest.raises(ValueError):
        load_sources(tmp_path)


def test_csv_validation_empty_missing_duplicates_and_counts(tmp_path):
    root = input_root(tmp_path)
    manifest = make_fixture(root)
    path = root / manifest["directory"] / "exmergo/dex/ghrs-data/views_clones_aggregate.csv"
    original = path.read_text()
    header = original.splitlines()[0] + "\n"
    path.write_text(header)
    tables, _ = parse_inputs(root, manifest)
    assert len(tables["traffic"]) == 60  # Other repository still has all its observations.
    for row in [
        "2026-07-01T00:00:00Z,0,1,0,0\n",
        "2026-07-01T00:00:00Z,-1,0,1,1\n",
        "2026-07-01T01:00:00Z,1,1,1,1\n",
        "2026-07-01T00:00:00Z,1,1,1,1\n2026-07-01T00:00:00Z,1,1,1,1\n",
    ]:
        path.write_text(header + row)
        with pytest.raises(ValueError):
            parse_inputs(root, manifest)
    path.unlink()
    with pytest.raises(FileNotFoundError):
        parse_inputs(root, manifest)


def test_manifest_integrity(tmp_path):
    root = input_root(tmp_path)
    manifest = sync(root, client=FakeGitHub(upstream_files()), supplement=False)
    path = root / manifest["directory"] / "exmergo/dex/ghrs-data/views_clones_aggregate.csv"
    path.write_text(path.read_text().replace(",0,0,0,0", ",1,0,0,0"))
    with pytest.raises(ValueError, match="checksum"):
        parse_inputs(root, manifest)


def test_release_pagination_fails_closed():
    client = GitHub()
    client.json = lambda route: [{"id": int(route.split("page=")[-1]), "draft": False}] * 100
    with pytest.raises(SourceError, match="pagination"):
        client.releases("exmergo/dex")
    pages = [
        [{"id": 1, "draft": False}] * 100,
        [{"id": 2, "draft": True}, {"id": 3, "draft": False}],
    ]
    client.json = lambda route: pages.pop(0)
    assert len(client.releases("exmergo/dex")) == 101


def test_auth_failure_and_transient_retry():
    unauthorized = urllib.error.HTTPError("https://api.github.com/test", 401, "No", {}, None)
    with patch("urllib.request.urlopen", side_effect=unauthorized):
        with pytest.raises(SourceError, match="token expiry"):
            GitHub("secret").json("/test")
    transient = urllib.error.HTTPError("https://api.github.com/test", 503, "Later", {}, None)
    with patch("urllib.request.urlopen", side_effect=transient) as call, patch("time.sleep"):
        with pytest.raises(SourceError, match="503"):
            GitHub().json("/test")
        assert call.call_count == 3


def test_private_project_rejected_before_collection(tmp_path):
    from oss_analytics.sources import require_public_sources

    root = input_root(tmp_path)
    client = GitHub()
    client.json = lambda route: {"private": False}
    require_public_sources(root, destination="exmergo/analytics", client=client)
    client.json = lambda route: {"private": route.endswith("exmergo/dex")}
    with pytest.raises(SourceError, match="public repositories"):
        require_public_sources(root, destination="exmergo/analytics", client=client)


def test_multi_repository_ci_candidate_uses_one_pinned_commit(tmp_path):
    root = input_root(tmp_path)
    (root / "sources.yml").write_text(
        "repositories:\n  - repository: exmergo/dex\n    mode: collect\n"
        "  - repository: example/other\n    mode: collect\n"
    )
    files = upstream_files()
    files["example/other/ghrs-data/views_clones_aggregate.csv"] = next(iter(files.values()))
    with pytest.raises(ValueError, match="exactly one"):
        sync(root, revision=SHA, client=FakeGitHub(files), supplement=False)
    candidate = sync(
        root,
        revision=SHA,
        data_repository="exmergo/analytics",
        client=FakeGitHub(files),
        supplement=False,
        internal_candidate=True,
    )
    assert len(candidate["sources"]) == 2
    assert {s["source_revision"] for s in candidate["sources"]} == {SHA}
    tables, _ = parse_inputs(root, candidate)
    assert {r[0] for r in tables["traffic"]} == {"exmergo/dex", "example/other"}

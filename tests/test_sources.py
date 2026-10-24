import hashlib
import io
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
    def __init__(
        self, files, *, publication=None, truncated=False, subtree_truncated=None, private=False
    ):
        self.files = files
        self.publication = publication
        self.private = private
        self.truncated = truncated
        # By default a truncated root also truncates the repository subtree.
        self.subtree_truncated = truncated if subtree_truncated is None else subtree_truncated
        self.routes = []

    def json(self, route, **kwargs):
        self.routes.append(route)
        if route.count("/") == 3:
            return {"private": self.private}
        if "/commits/" in route:
            return {"sha": SHA}
        if "/git/trees/" in route:
            node = route.split("/git/trees/")[1].split("?")[0]
            root = not node.startswith("tree:")
            if root and route.endswith("recursive=1"):
                return {
                    "truncated": self.truncated,
                    "tree": [{"path": p, "type": "blob"} for p in self.files],
                }
            # Non-recursive listings descend one directory; node names stand in for SHAs.
            prefix = "" if root else node.removeprefix("tree:") + "/"
            if route.endswith("recursive=1"):
                return {
                    "truncated": self.subtree_truncated,
                    "tree": [
                        {"path": p[len(prefix) :], "type": "blob"}
                        for p in self.files
                        if p.startswith(prefix)
                    ],
                }
            names = {p[len(prefix) :].split("/")[0] for p in self.files if p.startswith(prefix)}
            return {
                "tree": [{"path": n, "type": "tree", "sha": "tree:" + prefix + n} for n in names]
            }
        raise AssertionError(route)

    def get(self, url, **kwargs):
        if url.endswith("/published.json"):
            return json.dumps(self.publication).encode() if self.publication else None
        # Assert downloads are pinned, not made from a moving branch name.
        assert "/" + SHA + "/" in url or self.publication
        return self.files[url.split("/", 6)[6]]

    def contents(self, repository, ref, path, **kwargs):
        assert self.private, "public data branches are read from raw content"
        self.routes.append(f"contents:{ref}:{path}")
        if path == "published.json":
            return json.dumps(self.publication).encode() if self.publication else None
        assert ref == SHA or self.publication
        return self.files[path]


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


def test_large_branch_lists_only_the_repository_subtree(tmp_path):
    root = input_root(tmp_path)
    files = upstream_files()
    files["other/project/ghrs-data/views_clones_aggregate.csv"] = b"unrelated"
    client = FakeGitHub(files, truncated=True, subtree_truncated=False)
    manifest = sync(root, client=client, supplement=False)
    assert list(manifest["sources"][0]["files"]) == [
        "exmergo/dex/ghrs-data/views_clones_aggregate.csv"
    ]
    assert any(r.endswith("/git/trees/tree:exmergo/dex?recursive=1") for r in client.routes)


def test_case_mismatched_upstream_folder_lands_under_configured_name(tmp_path):
    root = input_root(tmp_path)
    files = {k.replace("exmergo/dex", "Exmergo/Dex"): v for k, v in upstream_files().items()}
    manifest = sync(root, client=FakeGitHub(files), supplement=False)
    assert "exmergo/dex/ghrs-data/views_clones_aggregate.csv" in manifest["sources"][0]["files"]


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
    body = io.BytesIO(b'{"message": "Resource not accessible by\\npersonal access token"}')
    refused = urllib.error.HTTPError("https://api.github.com/test", 403, "No", {}, body)
    with patch("urllib.request.urlopen", side_effect=refused):
        with pytest.raises(SourceError, match='403 \\("Resource not accessible by personal access'):
            GitHub("secret").json("/test")
    transient = urllib.error.HTTPError("https://api.github.com/test", 503, "Later", {}, None)
    with patch("urllib.request.urlopen", side_effect=transient) as call, patch("time.sleep"):
        with pytest.raises(SourceError, match="503"):
            GitHub().json("/test")
        assert call.call_count == 3


def test_private_project_only_rejected_from_a_public_destination(tmp_path):
    from oss_analytics.sources import require_safe_visibility

    root = input_root(tmp_path)
    client = GitHub()
    private = set()
    client.json = lambda route: {"private": route.removeprefix("/repos/") in private}
    require_safe_visibility(root, destination="exmergo/analytics", client=client)
    private = {"exmergo/dex"}
    with pytest.raises(SourceError, match="^exmergo/dex: .*public analytics repository"):
        require_safe_visibility(root, destination="exmergo/analytics", client=client)
    # Nothing leaks when the analytics repository is private too, or when run locally.
    private = {"exmergo/dex", "exmergo/analytics"}
    require_safe_visibility(root, destination="exmergo/analytics", client=client)
    require_safe_visibility(root, client=client)
    private = {"exmergo/analytics"}
    require_safe_visibility(root, destination="exmergo/analytics", client=client)

    def missing(route):
        if route.endswith("exmergo/analytics"):
            raise SourceError("api.github.com HTTP 404")
        return {"private": False}

    client.json = missing
    with pytest.raises(SourceError, match="^exmergo/analytics: api.github.com HTTP 404"):
        require_safe_visibility(root, destination="exmergo/analytics", client=client)


def test_private_data_branch_is_read_through_the_api(tmp_path):
    root = input_root(tmp_path)
    source = load_sources(root)[0]
    approved = "b" * 40
    client = FakeGitHub(upstream_files(), publication={"data_commit": approved}, private=True)
    result = import_source(root, source, root / ".data/input", client=client)
    assert result["source_revision"] == approved
    assert f"contents:{SHA}:published.json" in client.routes
    assert f"contents:{approved}:exmergo/dex/ghrs-data/views_clones_aggregate.csv" in client.routes


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


def test_rate_limit_retries_and_http_date_retry_after():
    from email.utils import format_datetime
    from datetime import datetime, timedelta, timezone

    limited = urllib.error.HTTPError(
        "https://api.github.com/test", 403, "Limited", {"x-ratelimit-remaining": "0"}, None
    )
    later = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=5), usegmt=True)
    throttled = urllib.error.HTTPError(
        "https://api.github.com/test", 429, "Later", {"Retry-After": later}, None
    )

    class Response:
        url = "https://api.github.com/test"
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            return b"[]"

    with (
        patch("urllib.request.urlopen", side_effect=[limited, throttled, Response()]) as call,
        patch("time.sleep") as sleep,
    ):
        assert GitHub().json("/test") == []
    assert call.call_count == 3
    assert 0 < sleep.call_args_list[1].args[0] <= 6
    distant = urllib.error.HTTPError(
        "https://api.github.com/test",
        403,
        "Limited",
        {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "9999999999"},
        None,
    )
    with patch("urllib.request.urlopen", side_effect=distant), patch("time.sleep"):
        with pytest.raises(SourceError, match="rate limit resets"):
            GitHub().json("/test")


def test_package_hosts_receive_no_token_and_others_are_refused():
    seen = {}

    def opener(request, timeout):
        seen.update(dict(request.header_items()))
        raise urllib.error.HTTPError(request.full_url, 404, "No", {}, None)

    with patch("urllib.request.urlopen", side_effect=opener):
        GitHub("secret").get("https://pypistats.org/api/packages/x/overall", optional=True)
    assert "Authorization" not in seen
    with pytest.raises(SourceError, match="allowed"):
        GitHub().get("https://example.com/x")


class SignalClient:
    """Public endpoints the signal collector uses, with Link-free single pages."""

    def __init__(self, issues, *, registry_error=False):
        self.issues = issues
        self.registry_error = registry_error
        self.urls = []

    def paginate(self, route, accept="", max_pages=100):
        self.urls.append(route)
        if "/stargazers" in route:
            assert accept == "application/vnd.github.star+json"
            return [
                {"starred_at": "2026-07-01T23:30:00Z", "user": {"login": "a"}},
                {"starred_at": "2026-07-01T01:00:00Z", "user": {"login": "b"}},
                {"starred_at": "2026-07-03T00:00:00Z", "user": {"login": "c"}},
            ], True
        if "/forks" in route:
            return [{"created_at": "2026-07-02T10:00:00Z", "owner": {"login": "d"}}], True
        if "/issues" in route:
            return self.issues, True
        raise AssertionError(route)

    def json_url(self, url, optional=False):
        self.urls.append(url)
        if self.registry_error:
            raise SourceError("pypistats.org HTTP 503; retry later")
        return {
            "data": [
                {"category": "without_mirrors", "date": "2026-07-01", "downloads": 4},
                {"category": "with_mirrors", "date": "2026-07-01", "downloads": 9},
            ]
        }


def issue(number, updated, association, merged=None):
    return {
        "number": number,
        "created_at": "2026-07-01T00:00:00Z",
        "updated_at": updated,
        "closed_at": merged,
        "author_association": association,
        "user": {"login": "someone"},
        "title": "private words",
        "pull_request": {"merged_at": merged},
    }


def test_signals_store_aggregates_and_merge_incrementally(tmp_path):
    from oss_analytics.config import Source
    from oss_analytics.sources import collect_signals, read_csv

    source = Source("exmergo/dex", packages={"pypi": ["exmergo-dex-core"]})
    client = SignalClient([issue(7, "2026-07-01T05:00:00Z", "FIRST_TIME_CONTRIBUTOR")])
    first = collect_signals(client, source, tmp_path, "2026-07-04T00:00:00+00:00")
    folder = tmp_path / "exmergo/dex/signals"
    assert read_csv(folder / "stargazers.csv") == [
        {"date": "2026-07-01", "stars": "2"},
        {"date": "2026-07-03", "stars": "1"},
    ]
    stored = "".join(p.read_text() for p in folder.rglob("*.csv"))
    assert "someone" not in stored and "private words" not in stored and "login" not in stored
    assert first["packages"]["pypi:exmergo-dex-core"]["days"] == 1
    assert not any("npmjs" in u for u in client.urls)
    # GitHub later recomputes the association; the first observation is kept.
    client = SignalClient(
        [issue(7, "2026-07-05T00:00:00Z", "CONTRIBUTOR", merged="2026-07-05T00:00:00Z")],
        registry_error=True,
    )
    second = collect_signals(client, source, tmp_path, "2026-07-06T00:00:00+00:00")
    assert any("since=2026-07-01T04:00:00Z" in u for u in client.urls)
    rows = read_csv(folder / "issues.csv")
    assert rows[0]["author_association"] == "FIRST_TIME_CONTRIBUTOR"
    assert rows[0]["merged_at"] == "2026-07-05T00:00:00Z"
    assert second["errors"] and "pypi:exmergo-dex-core" in second["packages"]
    assert read_csv(folder / "downloads/pypi/exmergo-dex-core.csv") == [
        {"date": "2026-07-01", "downloads": "4"}
    ]


@pytest.mark.parametrize(
    "packages",
    ["{pypi: [ok], cargo: [x]}", "{pypi: ['bad name']}", "{npm: [Upper]}", "{pypi: [a, A]}"],
)
def test_invalid_packages(tmp_path, packages):
    (tmp_path / "sources.yml").write_text(
        f"repositories:\n  - repository: exmergo/dex\n    packages: {packages}\n"
    )
    with pytest.raises(ValueError):
        load_sources(tmp_path)


def test_counts_accept_integral_floats_only():
    from oss_analytics.warehouse import count

    assert count("3.0") == 3
    for value in ["3.5", "-1", "", True]:
        with pytest.raises(ValueError):
            count(value)


def test_blob_cache_skips_unchanged_downloads_and_checks_integrity(tmp_path):
    from oss_analytics.sources import git_blob_sha

    root = input_root(tmp_path)
    data = next(iter(upstream_files().values()))
    path = "exmergo/dex/ghrs-data/views_clones_aggregate.csv"

    class Hashed(FakeGitHub):
        downloads = 0

        def json(self, route, **kwargs):
            tree = super().json(route, **kwargs)
            for entry in tree.get("tree", []):
                entry["sha"] = self.blob
            return tree

        def get(self, url, **kwargs):
            if not url.endswith("/published.json"):
                Hashed.downloads += 1
            return super().get(url, **kwargs)

    client = Hashed({path: data})
    client.blob = git_blob_sha(data)
    sync(root, client=client, supplement=False)
    sync(root, client=client, supplement=False)
    assert Hashed.downloads == 1
    tampered = Hashed({path: data})
    tampered.blob = "0" * 40
    with pytest.raises(SourceError, match="does not match"):
        sync(root, client=tampered, supplement=False)


def test_anonymous_run_skips_star_dates_and_keeps_previous_history(tmp_path):
    from oss_analytics.config import Source
    from oss_analytics.sources import collect_signals

    source = Source("exmergo/dex")
    collect_signals(SignalClient([]), source, tmp_path, "2026-07-04T00:00:00+00:00")
    anonymous = SignalClient([])
    anonymous.token = None
    record = collect_signals(anonymous, source, tmp_path, "2026-07-05T00:00:00+00:00")
    assert not any("stargazers" in u for u in anonymous.urls)
    assert "set GITHUB_TOKEN" in record["errors"][0]
    # The earlier history survives with the time it was actually collected.
    assert record["stargazers"]["captured_at"] == "2026-07-04T00:00:00+00:00"
    assert record["forks"]["captured_at"] == "2026-07-05T00:00:00+00:00"


def test_contents_reads_raw_file_with_the_token():
    response = io.BytesIO(b"data")
    response.url = "https://api.github.com/repos/exmergo/analytics/contents/a%20b.csv?ref=" + SHA
    response.headers = {}
    response.__enter__ = lambda: response
    with patch("urllib.request.urlopen") as call:
        call.return_value.__enter__.return_value = response
        assert GitHub("secret").contents("exmergo/analytics", SHA, "a b.csv") == b"data"
    request = call.call_args[0][0]
    assert request.full_url == response.url
    assert request.get_header("Authorization") == "Bearer secret"
    assert request.get_header("Accept") == "application/vnd.github.raw+json"

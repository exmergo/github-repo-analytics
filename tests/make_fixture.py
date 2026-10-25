"""Deterministic synthetic inputs; production imports always use the live example."""

from __future__ import annotations
import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from oss_analytics.io import write_json


def make_fixture(root: Path) -> dict:
    directory = root / ".data/inputs/fixture"
    sources = []
    for index, repo in enumerate(["exmergo/dex", "example/other"]):
        folder = directory / repo / "ghrs-data"
        folder.mkdir(parents=True, exist_ok=True)

        def csv_file(name, header, rows):
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(rows)

        first = date(2026, 7, 1)
        rows = []
        for day in range(60):
            d = first + timedelta(days=day)
            rows.append([d.isoformat() + "T00:00:00+00:00", 4 + index, 2, 10 + index, 3])
        csv_file(
            "views_clones_aggregate.csv",
            ["time_iso8601", "clones_total", "clones_unique", "views_total", "views_unique"],
            rows,
        )
        for filename, field in [
            ("stargazers.csv", "stars_cumulative"),
            ("forks.csv", "forks_cumulative"),
        ]:
            csv_file(
                filename,
                ["time_iso8601", field],
                [["2026-07-01T00:00:00Z", 1], ["2026-07-03T00:00:00Z", 3]],
            )
        for stamp, refs in [
            ("2026-07-01_042500", [("Google", 10, 5), ("gone.example", 8, 4)]),
            ("2026-07-02_042500", [("Google", 20, 8)]),
            ("2026-07-02_052500", [("Google", 21, 9)]),
            ("2026-07-16_052500", [("Google", 30, 10), ("gone.example", 7, 3)]),
            ("2026-07-17_052500", []),
        ]:
            csv_file(
                f"snapshots/{stamp}_top_referrers_snapshot.csv",
                ["referrer", "views_total", "views_unique"],
                refs,
            )
            csv_file(
                f"snapshots/{stamp}_top_paths_snapshot.csv",
                ["url_path", "views_total", "views_unique"],
                [("/" + repo, 22 + index, 10)] if refs else [],
            )
        for day, stars in [(1, 10), (2, 8), (4, 9)]:
            capture = f"2026-07-{day:02d}T04:25:00+00:00"
            write_json(
                directory / repo / "metadata" / f"{day}.json",
                {
                    "repository": repo,
                    "github_id": 100 + index,
                    "captured_at": capture,
                    "stars": stars + index,
                    "forks": day + index,
                    "watchers": 3 + index,
                    "open_issues_and_prs": 2,
                    "releases": [
                        {
                            "id": 1000 + index,
                            "tag_name": "v1.0.0",
                            "name": "First release",
                            "published_at": "2026-07-20T10:00:00Z",
                            "html_url": f"https://github.com/{repo}/releases/tag/v1.0.0",
                            "draft": False,
                            "prerelease": False,
                            # Cumulative balances: +5 between consecutive days 1 and 2, gap to 4.
                            "assets": [
                                {"id": 5000 + index, "download_count": {1: 10, 2: 15, 4: 30}[day]}
                            ],
                        }
                    ],
                },
            )
        signals = directory / repo / "signals"
        csv_file(
            "../signals/stargazers.csv",
            ["date", "stars"],
            [["2026-07-01", 2], ["2026-07-03", 1], ["2026-08-10", 3]]
            if index == 0
            else [["2026-07-05", 1]],
        )
        csv_file(
            "../signals/forks.csv",
            ["date", "forks"],
            # The capture day (2026-08-31) is partial and excluded from fork history.
            [["2026-07-02", 1], ["2026-08-31", 1]] if index == 0 else [],
        )
        csv_file(
            "../signals/issues.csv",
            ["number", "kind", "created_at", "closed_at", "merged_at", "author_association"],
            [
                [1, "issue", "2026-07-01T10:00:00Z", "2026-07-03T10:00:00Z", "", "MEMBER"],
                [
                    2,
                    "pull_request",
                    "2026-07-02T00:00:00Z",
                    "2026-07-02T12:00:00Z",
                    "2026-07-02T12:00:00Z",
                    "FIRST_TIME_CONTRIBUTOR",
                ],
                [
                    3,
                    "pull_request",
                    "2026-07-05T00:00:00Z",
                    "2026-07-06T00:00:00Z",
                    "",
                    "CONTRIBUTOR",
                ],
                [4, "issue", "2026-07-20T00:00:00Z", "", "", "NONE"],
                [
                    5,
                    "pull_request",
                    "2026-07-21T00:00:00Z",
                    "2026-07-22T12:00:00Z",
                    "2026-07-22T12:00:00Z",
                    "CONTRIBUTOR",
                ],
            ]
            if index == 0
            else [],
        )
        packages = {}
        if index == 0:
            first_download = date(2026, 7, 1)
            csv_file(
                "../signals/downloads/pypi/exmergo-dex-core.csv",
                ["date", "downloads"],
                [[(first_download + timedelta(days=d)).isoformat(), 5] for d in range(28)],
            )
            packages = {"pypi:exmergo-dex-core": {"days": 28, "latest": "2026-07-28"}}
        write_json(
            signals / "deployments.json",
            {
                "environment": "production",
                "default_branch": "main",
                "deployments": [
                    {
                        "deployment_id": n,
                        "environment": "production",
                        "sha": "a" * 40,
                        "succeeded_at": stamp,
                    }
                    for n, stamp in [
                        (10, "2026-07-03T12:00:00Z"),
                        (11, "2026-07-04T12:00:00Z"),
                        (12, "2026-07-05T12:00:00Z"),
                        (13, "2026-07-06T12:00:00Z"),
                        (14, "2026-08-31T01:00:00Z"),
                    ]
                ],
                "changes": [
                    {
                        "deployment_id": dep,
                        "number": number,
                        "merged_at": merged,
                        "merge_sha": "b" * 40,
                    }
                    for dep, number, merged in (
                        [
                            (10, 101, "2026-07-03T10:00:00Z"),
                            (10, 102, "2026-07-03T08:00:00Z"),
                            (11, 101, "2026-07-03T10:00:00Z"),
                            (11, 102, "2026-07-03T08:00:00Z"),
                            (13, 103, "2026-07-05T12:00:00Z"),
                        ]
                        if index == 0
                        else [(10, 101, "2026-07-01T12:00:00Z")]
                    )
                ],
            },
        )
        write_json(
            signals / "capture.json",
            {
                "captured_at": "2026-08-31T04:25:00+00:00",
                "errors": [],
                "stargazers": {"complete": True, "listed": 6 if index == 0 else 1},
                "forks": {"complete": True, "listed": 2 if index == 0 else 0},
                "issues": {"complete": True, "through": "2026-08-31T04:00:00Z", "items": 5},
                "packages": packages,
                "deployments": {
                    "complete": True,
                    "environment": "production",
                    "default_branch": "main",
                },
            },
        )
        sources.append(
            {
                "repository": repo,
                "github_id": 100 + index,
                "source_revision": str(index + 1) * 40,
                "expected_refresh_hours": 24,
                "data_repository": repo,
                "files": {},
            }
        )
    manifest = {
        "version": 1,
        "synced_at": "2026-08-31T05:00:00+00:00",
        "directory": ".data/inputs/fixture",
        "sources": sources,
    }
    write_json(root / ".data/sync.json", manifest)
    write_json(directory / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(
        json.dumps(
            make_fixture(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()), indent=2
        )
    )

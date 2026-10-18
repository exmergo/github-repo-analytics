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
                    "releases": [
                        {
                            "id": 1000 + index,
                            "tag_name": "v1.0.0",
                            "name": "First release",
                            "published_at": "2026-07-20T10:00:00Z",
                            "html_url": f"https://github.com/{repo}/releases/tag/v1.0.0",
                            "draft": False,
                            "prerelease": False,
                        }
                    ],
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

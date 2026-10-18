"""Atomic state files and a bounded public GitHub client."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


class SourceError(RuntimeError):
    pass


def read_json(path: Path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


class GitHub:
    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    def get(self, url: str, *, optional: bool = False) -> bytes | None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in {
            "api.github.com",
            "raw.githubusercontent.com",
        }:
            raise SourceError("only HTTPS GitHub API and public raw-content URLs are allowed")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "exmergo-oss-analytics"}
        if parsed.hostname == "api.github.com":
            headers["X-GitHub-Api-Version"] = "2022-11-28"
            if self.token:
                headers["Authorization"] = "Bearer " + self.token
        for attempt in range(3):
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(url, headers=headers), timeout=30
                ) as r:
                    if urlparse(r.url).hostname != parsed.hostname:
                        raise SourceError("unexpected redirect host")
                    data = r.read(32 * 1024 * 1024 + 1)
                    if len(data) > 32 * 1024 * 1024:
                        raise SourceError("source file exceeds 32 MiB")
                    return data
            except urllib.error.HTTPError as exc:
                if optional and exc.code == 404:
                    return None
                if exc.code in {401, 403, 404}:
                    raise SourceError(
                        f"GitHub HTTP {exc.code}: check repository access, token expiry, "
                        "and API rate limits; previous valid inputs are retained"
                    ) from None
                if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise SourceError(f"GitHub HTTP {exc.code}; retry sync later") from None
                delay = min(int(exc.headers.get("Retry-After", "2")), 10)
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt == 2:
                    raise SourceError(
                        "GitHub is unreachable; retry sync when networking is available"
                    ) from None
                delay = 2**attempt
            time.sleep(max(0, delay))
        raise SourceError("GitHub request exhausted retries")

    def json(self, route: str, *, optional: bool = False):
        data = self.get("https://api.github.com" + route, optional=optional)
        return json.loads(data) if data is not None else None

    def releases(self, repository: str) -> list[dict]:
        result = []
        for page in range(1, 101):
            rows = self.json(f"/repos/{repository}/releases?per_page=100&page={page}")
            if not isinstance(rows, list):
                raise SourceError("unexpected GitHub releases response")
            result.extend(r for r in rows if not r["draft"])
            if len(rows) < 100:
                return result
        raise SourceError("release pagination exceeded 10,000 records; inputs were not promoted")

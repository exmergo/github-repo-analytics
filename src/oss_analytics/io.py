"""Atomic state files and a bounded public GitHub client."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote, urlparse

GITHUB_HOSTS = {"api.github.com", "raw.githubusercontent.com"}
# Package registries are contacted only when a repository configures the add-on.
PACKAGE_HOSTS = {"pypistats.org", "api.npmjs.org"}
NEXT_LINK = re.compile(r'<([^>]+)>;\s*rel="next"')


class SourceError(RuntimeError):
    pass


def read_json(path: Path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def publication_provenance(value: dict | None) -> dict | None:
    """Keep the approved revision's identity, without copying its source manifests."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("publication metadata must be a mapping")
    fields = ("version", "data_commit", "code_commit", "lockfile", "lock_sha256", "validated_at")
    result = {key: value[key] for key in fields if key in value}
    if any(isinstance(item, (dict, list)) for item in result.values()):
        raise ValueError("publication provenance fields must be scalar")
    return result


def retry_delay(headers, attempt: int) -> float:
    """Seconds to wait from Retry-After (seconds or HTTP-date) or a rate-limit reset."""
    value = (headers or {}).get("Retry-After")
    if value:
        try:
            return float(value)
        except ValueError:
            try:
                return (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError):
                pass
    reset = (headers or {}).get("x-ratelimit-reset")
    if reset and str(reset).isdigit():
        return int(reset) - time.time()
    return 2**attempt


def rate_limited(exc: urllib.error.HTTPError) -> bool:
    headers = exc.headers or {}
    return exc.code == 429 or (
        exc.code == 403
        and (headers.get("x-ratelimit-remaining") == "0" or headers.get("Retry-After") is not None)
    )


def error_message(exc: urllib.error.HTTPError) -> str:
    """GitHub explains a refusal in its JSON body; keep one bounded line of it."""
    try:
        message = json.loads(exc.read(4096)).get("message", "")
    except (AttributeError, OSError, TypeError, ValueError):
        return ""
    if not isinstance(message, str):
        return ""
    message = " ".join(message.split())[:200]
    return f' ("{message}")' if message else ""


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


class GitHub:
    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    def get(self, url: str, *, optional: bool = False) -> bytes | None:
        return self.request(url, optional=optional)[0]

    def request(
        self, url: str, *, optional: bool = False, accept: str = "application/vnd.github+json"
    ) -> tuple[bytes | None, dict]:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in GITHUB_HOSTS | PACKAGE_HOSTS:
            raise SourceError(
                "only HTTPS GitHub, public raw-content, and package-statistics URLs are allowed"
            )
        headers = {"Accept": accept, "User-Agent": "exmergo-oss-analytics"}
        if parsed.hostname == "api.github.com":
            headers["X-GitHub-Api-Version"] = "2022-11-28"
            # Tokens are sent only to the GitHub API, never to raw content or registries.
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
                    return data, dict(r.headers or {})
            except urllib.error.HTTPError as exc:
                if optional and exc.code == 404:
                    return None, {}
                if rate_limited(exc) and attempt < 2:
                    delay = retry_delay(exc.headers, attempt)
                    if delay > 60:
                        raise SourceError(
                            f"{parsed.hostname} rate limit resets in {int(delay)}s; set "
                            "GITHUB_TOKEN or retry later; previous valid inputs are retained"
                        ) from None
                elif exc.code in {401, 403, 404}:
                    raise SourceError(
                        f"{parsed.hostname} HTTP {exc.code}{error_message(exc)}: check "
                        "repository access (fine-grained tokens must include the repository), token "
                        "expiry, and API rate limits; previous valid inputs are retained"
                    ) from None
                elif exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise SourceError(f"{parsed.hostname} HTTP {exc.code}; retry later") from None
                else:
                    delay = min(retry_delay(exc.headers, attempt), 10)
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt == 2:
                    raise SourceError(
                        f"{parsed.hostname} is unreachable; retry when networking is available"
                    ) from None
                delay = 2**attempt
            time.sleep(max(0, delay))
        raise SourceError("request exhausted retries")

    def paginate(
        self, route: str, *, accept: str = "application/vnd.github+json", max_pages: int = 100
    ) -> tuple[list, bool]:
        """Follow Link headers; returns rows and whether every page was read."""
        url = "https://api.github.com" + route
        rows = []
        for _ in range(max_pages):
            data, headers = self.request(url, accept=accept)
            page = json.loads(data)
            if not isinstance(page, list):
                raise SourceError(f"unexpected GitHub response for {route}")
            rows.extend(page)
            link = NEXT_LINK.search(headers.get("Link") or headers.get("link") or "")
            if not link:
                return rows, True
            url = link[1]
            if urlparse(url).hostname != "api.github.com":
                raise SourceError("unexpected pagination host")
        return rows, False

    def json(self, route: str, *, optional: bool = False):
        return self.json_url("https://api.github.com" + route, optional=optional)

    def contents(self, repository: str, ref: str, path: str, *, optional: bool = False):
        """Read one file at a commit through the API, which unlike raw content takes the token."""
        url = (
            f"https://api.github.com/repos/{repository}/contents/{quote(path, safe='/')}"
            f"?ref={quote(ref, safe='')}"
        )
        return self.request(url, optional=optional, accept="application/vnd.github.raw+json")[0]

    def json_url(self, url: str, *, optional: bool = False):
        data = self.get(url, optional=optional)
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

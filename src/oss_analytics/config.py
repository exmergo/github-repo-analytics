"""Validated, non-secret source configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REVISION = re.compile(r"^[0-9a-f]{40}$")
# PyPI normalized names and npm names, including @scope/name.
PACKAGE = {
    "pypi": re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$"),
    "npm": re.compile(r"^(@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]*$"),
}


def validate_repository(repository: str) -> None:
    if not REPOSITORY.fullmatch(repository) or any(
        part in {".", ".."} for part in repository.split("/")
    ):
        raise ValueError(f"invalid owner/repository: {repository}")


@dataclass(frozen=True)
class Source:
    repository: str
    mode: str = "import"
    data_repository: str = ""
    data_branch: str = "github-repo-stats"
    expected_refresh_hours: int = 24
    # Optional add-on: {"pypi": [...], "npm": [...]}. Most projects publish to one or neither.
    packages: dict = field(default_factory=dict)

    # Opt-in GitHub deployment evidence; environment must be explicit.
    deployments: dict = field(default_factory=dict)

    def package_list(self) -> list[tuple[str, str]]:
        return [
            (registry, name) for registry in PACKAGE for name in self.packages.get(registry, [])
        ]


def load_sources(root: Path) -> list[Source]:
    value = yaml.safe_load((root / "sources.yml").read_text())
    if not isinstance(value, dict) or set(value) != {"repositories"}:
        raise ValueError("sources.yml must contain only a repositories list")
    rows = value["repositories"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("configure at least one repository")
    result = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("each repository configuration must be a mapping")
        source = Source(**row)
        for repo in [source.repository, source.data_repository or source.repository]:
            validate_repository(repo)
        if source.repository.lower() in seen:
            raise ValueError(f"duplicate repository: {source.repository}")
        if source.mode not in {"import", "collect"}:
            raise ValueError("mode must be import or collect")
        if not isinstance(source.expected_refresh_hours, int) or source.expected_refresh_hours < 1:
            raise ValueError("expected_refresh_hours must be a positive integer")
        if not source.data_branch or source.data_branch.startswith("-"):
            raise ValueError("invalid source branch")
        if not isinstance(source.packages, dict) or set(source.packages) - set(PACKAGE):
            raise ValueError("packages supports only pypi and npm lists")
        for registry, names in source.packages.items():
            if not isinstance(names, list) or not all(
                isinstance(n, str) and PACKAGE[registry].fullmatch(n) for n in names
            ):
                raise ValueError(f"invalid {registry} package list for {source.repository}")
            if len({n.lower() for n in names}) != len(names):
                raise ValueError(f"duplicate {registry} package for {source.repository}")
        if not isinstance(source.deployments, dict):
            raise ValueError("deployments must be a mapping")
        if source.deployments:
            if set(source.deployments) != {"source", "environment"}:
                raise ValueError("deployments requires source and environment only")
            if source.deployments["source"] != "github":
                raise ValueError(
                    "deployments supports only source: github; workflows/releases unsupported"
                )
            environment = source.deployments["environment"]
            if not isinstance(environment, str) or not environment.strip():
                raise ValueError("deployments environment must be a nonempty exact name")
        seen.add(source.repository.lower())
        result.append(source)
    return result

# Native uv migration

`uv.lock` is now the sole dependency lockfile. `pyproject.toml` declares direct dependencies and development tools; its duplicate transitive constraints and the former `requirements.lock` are removed. The initial lock was generated with network access in the maintainer's terminal, then re-resolved by uv from cached registry metadata after removing the redundant constraints. The lockfile was not hand-authored or patched.

[resolution-comparison.json](resolution-comparison.json) records the comparison with the former requirements lock. Existing resolved dependency versions are unchanged. Setuptools remains the exactly pinned build backend in `pyproject.toml` and is no longer installed as an unnecessary runtime dependency. The lock also includes platform-conditional dependencies and wheel hashes.

The bootstrap and both workflows install with `uv sync --locked`. CLI examples and CI execution use `uv run --frozen`. CI pins uv 0.13.1 and exercises Python 3.11 and 3.12; local validation below uses Python 3.11. Publication names `uv.lock` and hashes its exact bytes. A new regression test verifies that changing it invalidates analytics readiness, answers, and publication until the project is rebuilt and checked.

| Evidence | What ran |
|---|---|
| [lock-check.log](lock-check.log) | `uv lock --check --offline` checks that the generated lock matches the declarations. |
| [sync.log](sync.log) | `uv sync --locked --offline` builds and installs the editable project through uv's isolated build environment. |
| [bootstrap.log](bootstrap.log) | The actual `bash scripts/bootstrap.sh` succeeds with the locked environment. |
| [lint.log](lint.log) | Frozen Ruff lint and formatting checks. |
| [tests.log](tests.log) | The integration suite executed using `uv run --frozen pytest -q`. The live-network test remains opt-in. |
| [build.json](build.json) | The candidate build invokes Dex, passes dbt tests and verification, and executes every MetricFlow metric before replacing the warehouse. |
| [check.json](check.json) | Dex maintenance and verification against the existing accepted baseline. No replacement baseline was needed or taken for this dependency migration. |
| [status.json](status.json) | Readiness against the current code and native lockfile digest. |

Final validation: **36 tests passed, one opt-in live-network test skipped**. Lint, formatting, lock freshness, bootstrap, the Dex build (48 dbt checks), all 17 MetricFlow executions, and maintenance passed. Verification reports zero findings while retaining the limitations below.

The parent audit's approximate/exact discovery cardinality notices, empty supplemental sources, and unresolved join-verification warnings remain visible. Dependency migration does not clear or override them. The original audit envelopes are historical evidence and retain their original commands.

Review `pyproject.toml`, `uv.lock`, removal of `requirements.lock`, `scripts/bootstrap.sh`, workflows, lifecycle publication provenance, tests, documentation, and this evidence together as one dependency migration commit. Nothing was staged or committed by the agent.

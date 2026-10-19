# Contributing

Participation follows the [code of conduct](CODE_OF_CONDUCT.md). Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md). For a question the template cannot answer yet, open a *Question or metric request* issue first so the definition can be agreed before code.

Bootstrap with `bash scripts/bootstrap.sh`. Run `uv run --frozen pytest -q`, `uv run --frozen ruff check .`, and `uv run --frozen ruff format --check .` before proposing a change.

Metric changes need numerical expectations exercised through Dex/MetricFlow, including their allowed dimensions, period aggregation, missing observations, and zero denominators. Preserve the distinction between daily counts, observed balances, and rolling snapshots. Update the metric contract and question cookbook with any public interface changes.

Normal tests require no network or credentials. The explicit `--live` smoke test downloads the changing public Dex example and checks behavior without asserting changing production numbers. Do not add credentials, personal identifiers, DuckDB files, raw production data, or Python/runtime caches to a pull request. Dex's maps, reviewed plans, drift reports, and accepted baseline are engineering evidence and remain visible to Git.

Use the installed Explore, Transform, and Maintain skills for analytics changes. Verify source columns and grains with Dex before preparing an edit payload. Read and apply the Dex plan, build on dev with verification, and inspect maintenance against the previous baseline. Include the plan and relevant evidence with the change; preserve warnings and skipped checks. A passing dbt build does not establish that every join was verified. See [the audit index](.dex/review/README.md) for the existing project's evidence.

Declare dependencies in `pyproject.toml` and commit the generated `uv.lock`. Use `uv lock --upgrade-package <name>` for a deliberate package update, then `uv sync --locked` and the real query suite on both supported Python versions. Review the lock diff; do not maintain a second requirements lock. Workflow action upgrades must pin the reviewed commit. Keep Apache-2.0 attribution and upstream notices.

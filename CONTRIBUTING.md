# Contributing

Participation follows the [code of conduct](CODE_OF_CONDUCT.md). Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md). For a question the template cannot answer yet, open a *Question or metric request* issue first so the definition can be agreed before code.

## Set up Dex

Every model and metric in this repository is changed through [Dex](https://github.com/exmergo/dex), the open-source analytics engineering toolkit for coding agents. Set it up before you start, including for a change that looks small: pull requests that change models or metrics without a Dex plan and maintenance evidence can't be reviewed.

1. **Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/)** 0.13.1 or later.
2. **Bootstrap:** `bash scripts/bootstrap.sh`. This installs the Dex engine pinned in `uv.lock`, so `uv run --frozen dex …` runs the exact version CI uses.
3. **Install the Dex skills in your coding agent**, so it can Explore, Transform, and Maintain:
   - **Claude Code**, inside Claude Code: `/plugin marketplace add exmergo/exmergo-agent-plugins`, then `/plugin install dex@exmergo`. The skills appear as `/dex:explore`, `/dex:transform`, and `/dex:maintain`.
   - **Codex:** `npx skills add exmergo/dex --agent codex`.
   - **Any other agent:** `npx skills add exmergo/dex`, or point it at [AGENTS.md](AGENTS.md).

   This repository also vendors the skills under `.agents/skills/`, pinned by `skills-lock.json`, for agents that read that folder.
4. **Build and check:** `uv run --frozen oss-analytics sync`, `build`, `baseline`, then `check`, as in the README. Then confirm Dex sees the warehouse with `uv run --frozen dex connect test`.

Inside this repository, always run Dex as `uv run --frozen dex`, so the engine matches the lock file even if your agent's plugin is newer.

## Before you propose a change

Run `uv run --frozen pytest -q`, `uv run --frozen ruff check .`, and `uv run --frozen ruff format --check .`.

Metric changes need numerical expectations exercised through Dex/MetricFlow, including their allowed dimensions, period aggregation, missing observations, and zero denominators. Preserve the distinction between daily counts, observed balances, and rolling snapshots. Update the metric contract and question cookbook with any public interface changes.

Normal tests require no network or credentials. The explicit `--live` smoke test downloads the changing public Dex example and checks behavior without asserting changing production numbers. Do not add credentials, personal identifiers, DuckDB files, raw production data, or Python/runtime caches to a pull request. Dex's maps, reviewed plans, drift reports, and accepted baseline are engineering evidence and remain visible to Git.

Use the Dex Explore, Transform, and Maintain skills ([Set up Dex](#set-up-dex)) for analytics changes. Verify source columns and grains with Dex before preparing an edit payload. Read and apply the Dex plan, build on dev with verification, and inspect maintenance against the previous baseline. Include the plan and relevant evidence with the change; preserve warnings and skipped checks. A passing dbt build does not establish that every join was verified. See [the audit index](.dex/review/README.md) for the existing project's evidence.

Declare dependencies in `pyproject.toml` and commit the generated `uv.lock`. Use `uv lock --upgrade-package <name>` for a deliberate package update, then `uv sync --locked` and the real query suite on both supported Python versions. Review the lock diff; do not maintain a second requirements lock. Workflow action upgrades must pin the reviewed commit. Keep Apache-2.0 attribution and upstream notices.

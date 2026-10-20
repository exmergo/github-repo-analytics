## What changes

<!-- One or two sentences. Link the issue if there is one. -->

## Analytics engineering checklist

- [ ] Model, test, or metric changes were planned with `dex transform plan` / `dex semantic plan`, and the plan ID is: `p…`
- [ ] I read the plan's diffs, warnings, and `row_attribution`, and `transform build --target dev --verify` reported `verification.ran: true`.
- [ ] `uv run --frozen pytest -q`, `ruff check .`, and `ruff format --check .` pass.
- [ ] `oss-analytics check` passes, or this PR intentionally changes definitions and includes the reviewed `.dex/snapshot.json` plus the previous-baseline comparison.
- [ ] Docs (`docs/metrics.md`, `docs/questions.md`, `AGENTS.md`) describe any new metric's caveats.

## Baseline change

- [ ] No baseline change
- [ ] Baseline replaced: findings reviewed and listed below

<!-- Paste the `maintain check` findings you accepted, with why each is intended. -->

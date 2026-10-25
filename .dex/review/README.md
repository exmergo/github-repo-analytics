# Dex audit trail: adding stars, community, and downloads

The [issue 11 deployment lifecycle audit](issue-11/README.md) records the later addition of production deployment frequency and merge-to-deployment lead time, including its preserved baseline comparison.

This directory holds the actual Dex command output from one Explore → Transform → Maintain session (2026-10-19). That session took the template from traffic-only analytics to 39 governed metrics: star and fork history, issues and pull requests, release and package downloads, repository vitals, rolling and week-over-week metrics. Every model and metric change in the session went through a Dex plan. Nothing in the dbt project or semantic layer was hand-edited in place of the guarded command.

- **Engine:** `exmergo-dex-core==1.15.0`, both through the project lock (`uv run --frozen dex`) and through the Explore/Transform/Maintain skill launchers. Steps 40 to 49 ran on 1.15.2 (see [the maintenance pass](#maintenance-dex-1152-and-a-day-of-new-data-2026-10-22)).
- **Warehouse:** local DuckDB, built from the public `exmergo/dex` example plus live public signals. Run outside of any session, `oss-analytics status --json` reports the current readiness, coverage, source revision, and code digest.
- **Paths:** absolute paths in saved envelopes were rewritten to `.`, `~`, `<scratchpad>`, or `<dex-plugin-1.15.0>`. Nothing else was edited.

The previous session's trail (Dex 1.14) is in Git history. Its accepted baseline is kept as [previous-baseline.json](previous-baseline.json), and this session's changes were checked against it.

## Read the evidence in this order

| Step | Evidence | What it shows |
|---|---|---|
| Connect | [01](01-connect.json) | Read-only DuckDB connection, free local cost paradigm. |
| Inventory and map | [02](02-inventory.json), [03](03-map-before.json) | 24 objects, declared joins read from the semantic layer, zero PII columns. |
| Reference check | [04](04-check-reference-build.json) | The unchanged models rebuilt on 1.15.0 pass `check` against the previous baseline, so the engine upgrade alone changed nothing. |
| Explore new sources | [05](05-profile-new-raw-tables.json) | Profiles of the new raw tables before any SQL was written: grains (`date`, `number`), null fractions, value domains. Dex flagged `release_assets.asset_name` as a possible name (PII, confidence 0.6). No metric needs it, so ingestion drops the column instead of overriding the flag. |
| Staging plan | [06](06-staging-plan.json) → [07](07-staging-apply.json) → [08](08-staging-build-verify.json) | Plan `pd93b32993a`: six staging models plus contracts. The only change to an existing model is two additive columns on `stg_observations`. The build ran with `verification.ran: true` and zero findings. |
| Marts plan | [09](09-marts-plan.json) → [10](10-marts-apply.json) → [11](11-marts-build-verify.json) | Plan `p4ba3d1fc76`: star, fork, issue, release-download, and package-download marts. `row_attribution` proves `fct_legacy` keeps 33 → 33 rows after the refactor. Time-spine attribution was honestly reported as unmeasurable until the new marts existed. 28 models, 127 tests, zero verification findings. |
| Probe the marts | [12](12-marts-probes.json) | Star history sums to 88 and observed stars are 88. Forks reach 21 of 24 because the partial capture day is excluded by design. |
| Semantic plan | [13](13-semantic-plan.json) → [14](14-semantic-apply.json) → [15](15-semantic-build-verify.json) | Plan `p52de526669`: 27 definitions added, 2 updated additively, 21 unchanged, and the plan was parsed by dbt before being stored. |
| Maintain vs previous baseline | [16](16-check-against-previous-baseline.json) | Every schema and semantic finding is additive and matches the plans above. The volume jumps are the example finally having observations and releases. Two cardinality notices repeat the previous audit. |
| Reconcile | [17](17-reconcile.json) | 1 mechanical and 35 advisory proposals. **The mechanical proposal (plan `p854e61500e`) was reviewed and rejected:** re-scaffolding `stg_observations` would delete the hand-written `observation_source_key` that `fct_observations` relies on. It would also add a second `stg_observations.yml` that duplicates the model's contract in `schema.yml`, and assert `captured_at` unique, which is false across repositories. The drift it targets was already handled by plan `pd93b32993a`. The plan stays unapplied as a record. |
| Accept the change | [18](18-map-full.json), [19](19-baseline-accepted.json) | Full re-map (41 objects, zero PII columns), then the reviewed baseline. |
| A metric definition fix | [20](20-cumulative-definitions-refusal.json) → [21](21-cumulative-plan.json) → [22](22-cumulative-apply.json) → [23](23-cumulative-build-verify.json) | `stars_from_history` read 25, 25, 28, 74 by week because cumulative metrics default to the first day of each period. Plan `p93b1d13147` sets `period_agg: last`, and the running total is now 25, 25, 61, 88. The definitions splicer refused this file's layout ([20](20-cumulative-definitions-refusal.json)) and named the guarded whole-file route, which was used. Plan `p1863b2e333` was superseded by a wording fix and is unapplied. |
| Maintain catches it | [24](24-check-catches-definition-change.json) | `check` blocked on `definition_changed` for both cumulative metrics until the change was reviewed and the baseline accepted. |
| Mutation testing | [25](25-mutation-fct_snapshot_status.json), [26](26-mutation-semantic-backed-model.json) | `fct_snapshot_status` scores 1.0: both generated mutants were killed, none excluded or elided. Its key now hashes the declared daily grain, so the `unique` test catches a removed dedup. Models that back a semantic model cannot be mutated with this engine release (see limitations). |
| Whole-project verify | [27](27-verify.json) | Zero findings. Row population was **suppressed**, not checked: "no compiled model could be lined up against a driving parent". The per-build `--verify` runs above are the row-level evidence. |
| Relationships | [28](28-relationships-verified.json) | 16 joins, all verified, zero orphans. Joins from empty release-asset tables have no orphan fraction to measure. |
| Semantic catalog | [29](29-semantic-inventory.json), [30](30-diagram.json) | 39 metrics with their inputs and dimensions, and the entity diagram (Dex's own Mermaid; not redrawn). |
| Plans | [31](31-plans.json) | Engine plan listing: applied, rejected, and superseded plans. |
| Final state | [32](32-final-check.json), [33](33-status.json), [34](34-weekly-report.json) | `check` passes. `status` is ready and fresh with every signal captured. `weekly-report` answers all sections except release downloads, which are unavailable because Dex uploads no release assets. |

## Follow-up: adding a second repository (2026-10-22)

Adding `exmergo/github-repo-analytics` in `mode: collect` gave the warehouse a second repository. The scheduled run [39787868704](https://github.com/exmergo/github-repo-analytics/actions/runs/39787868704) collected both projects and kept their raw data, then refused to publish.

| Step | Evidence | What it shows |
|---|---|---|
| Maintain blocks | [35](35-check-blocks-second-repository.json) | `check` reports `key_lost_uniqueness` on `date` (traffic, star history) and `number` (issues). The one-repository baseline had recorded these single columns as unique. The same findings reproduced locally on the pinned candidate `8fb6923`. |
| Explore the cause | [36](36-grain-probe-per-repository.json) | Every duplicate is a different repository on the same date or issue number. Traffic has 134 rows: 134 distinct `(repository, date)` pairs but only 121 dates. Star history: 114 and 114, against 111 dates. Issues: 770 and 770, against 766 numbers. The models and their `(repository, …)` tests are correct; the baseline was behind. |
| Accept the reviewed change | [37](37-baseline-two-repositories.json), [38](38-check-two-repositories.json), [39](39-status-two-repositories.json) | New baseline, `check` passes, and `status` is ready with both projects fresh. The new project has 14 days of traffic, GitHub's full window, and complete star, fork, and issue signals. |

The one-repository baseline is kept as [previous-baseline-one-repository.json](previous-baseline-one-repository.json). No model or metric changed, so no Transform plan was needed.

## Maintenance: Dex 1.15.2 and a day of new data (2026-10-22)

A routine maintenance pass before v1.0.1. The engine moved from 1.15.0 to 1.15.2 in `pyproject.toml`, `uv.lock`, and the vendored skills, and the warehouse was rebuilt from the latest published data. No model, test, or metric changed.

| Step | Evidence | What it shows |
|---|---|---|
| Check against the old baseline | [40](40-check-dex-1.15.2-against-1.15.0-baseline.json) | All four axes ran under 1.15.2 against the 1.15.0 baseline. There was no `semantic_format_changed`, so the definitions were compared by content. 12 findings: 2 high, 4 medium, 6 low. |
| Explain the high findings | [41](41-probe-observation-capture-days.json) | `stars_net_change` and `forks_net_change` are NULL by design. `exmergo/dex` has captures on 2026-10-19 and 2026-10-22, and a net change needs consecutive days. Dex's hint that "its joined relation may have matched nothing" does not apply: the columns come from a `lag()` window, not from the join it names. |
| Name the new values | [42](42-probe-new-dimension-values.json) | `author_association` gained `FIRST_TIME_CONTRIBUTOR`, the first live first-time contributor PR, which `fct_issues` already counts. `dim_event` gained this repository's own v1.0.0 release and Dex v1.15.1 and v1.15.2. Paths and referrers are GitHub's rolling top 10. |
| Reconcile | [43](43-reconcile-all-advisory.json) | 0 mechanical and 12 advisory proposals, and no plan stored. Every finding is a decision about new data, and each was reviewed above. Compare step 17, where 1.15.0 proposed a mechanical re-scaffold that would have broken `stg_observations`. |
| Gate and verify | [44](44-gate-check-and-verify.json) | `oss-analytics check` passes against the old baseline: 39 metrics smoke-tested, and the only excused NULLs are the four source-proven ones. `maintain verify` returns no findings with nothing suppressed. Under 1.15.0, its row-population check was suppressed ([27](27-verify.json)). |
| Re-map and re-baseline | [45](45-map-full-refresh.json), [46](46-baseline-dex-1.15.2.json) | `explore map --use-project --full --refresh` re-scanned all 41 objects, because cached profiles under 24 hours old are otherwise reused. Then the snapshot was taken. |
| Check the new baseline | [47](47-check-after-baseline.json), [48](48-probe-exact-vs-approximate-distinct.json), [49](49-status.json) | `check` passes and `status` is ready. The two remaining medium cardinality notices compare an approximate baseline count with an exact live count on unchanged data: paths are 88 exact against 79 approximate, and referrers 23 against 24. That is Dex issue #640, not drift. |

The 1.15.0 baseline is kept as [previous-baseline-dex-1.15.0.json](previous-baseline-dex-1.15.0.json).

## What validation establishes, and what it does not

- [validation-tests.log](validation-tests.log): **53 passed, 1 skipped** (the opt-in live test, which passed separately against the public example). The suite runs real MetricFlow queries through Dex over a two-repository fixture. It asserts exact values for every new metric, gap and null behavior, recipe windows, anonymous collection, incremental issue merge, rate-limit retries, and the blob-cache integrity check. [validation-lint.log](validation-lint.log) covers ruff and actionlint.
- The final check still reports three high-severity `fully_null_column` findings. Each is excused only because the source proves the absence (fewer than two daily captures exist yet), and the excuse is recorded in the check output, not hidden.
- The two medium cardinality notices compare approximate profile counts with exact counts. The previous audit showed the same tables return 79 exact vs 69 approximate paths and 22 vs 23 referrers.
- Release-download metrics are verified by fixture values only. The live example has no uploaded release assets.

## Engine limitations found in this session (reported to Dex)

1. **Definitions splicing** refuses `models/semantic.yml` because the file uses indentless YAML sequences (`- name:` at column 0 under `semantic_models:` and `metrics:`). The refusal is safe and names `--edits-file`, which was used. Only a whole-file diff can be reviewed in that case.
2. **Mutation testing** wraps the mutated model as `materialized='ephemeral'`. A semantic model that `ref()`s an ephemeral model fails dbt's semantic manifest validation (`PydanticSemanticModel`), so no model backing a metric can be mutation-tested. Value tests in `tests/test_metrics.py` cover those models instead.
3. **Semantic query results are capped at 50 rows**, and `--limit` does not raise the cap. Recipes keep each query within one bounded window and refuse truncated results.
4. **Reconcile's mechanical re-scaffold** of a hand-written staging model drops key logic and adds a duplicate model YAML (see step 17). Read every mechanical proposal before applying it.

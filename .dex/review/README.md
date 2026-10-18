# Dex audit and corrections

This directory records an actual Explore → Transform → Maintain pass over the existing project. The initial implementation was authored directly; these plans are subsequent corrections, not evidence that its original authorship followed Dex's workflow. No Git staging or commits were performed during this audit.

The engine used here is the project's installed `exmergo-dex-core==1.14.0`, invoked through `uv run --no-sync dex` (or the Python orchestration that invokes that same CLI). The installed skills pin their standalone launcher to 1.14.1. That launcher could not download its engine because sandbox DNS cannot resolve PyPI; its actual stderr is retained in `00-skill-wrapper.stderr`. No raw database client substituted for Dex during this audit.

## Read the evidence in this order

| Step | Actual command response | What to review |
|---|---|---|
| Explore | [01-explore-before.json](01-explore-before.json) | Warehouse columns, grains, relationships, PII findings, and initial cache reuse. |
| Diagnose | [02-verify-before.json](02-verify-before.json) | Eight undeclared-column findings, seven models without column contracts, and unverified grains/joins. |
| Dependencies | [03-references.json](03-references.json) | Complete reference discovery for the staging models and traffic mart. |
| Old baseline | [04-check-before.json](04-check-before.json), [baseline-before.json](baseline-before.json) | The original drift comparison and the untouched previous baseline. |
| Model plan | [05-contracts-plan.json](05-contracts-plan.json), [06-contracts-apply.json](06-contracts-apply.json) | Applied plan `pea618a9ddd`: seven explicit staging projections, six complete grain keys, complete model column declarations, annotation seed types, and a traffic source-contract test. |
| Verified build | [07-build-verify.json](07-build-verify.json) | Dex built on dev and verification ran. Read `suppressed` and warnings as well as findings. |
| Semantic discovery | [08-semantic-inventory.json](08-semantic-inventory.json) | All 17 metrics, their inputs, aggregation time axes, and queryable dimensions. No catalog elements were elided. |
| Semantic plan | [09-semantic-plan.json](09-semantic-plan.json), [11-semantic-apply.json](11-semantic-apply.json) | Applied plan `p7ae49ddfc3`: clarify coverage and ratio-of-sums descriptions. Expressions and aggregations are unchanged. |
| Reconcile | [13-reconcile.json](13-reconcile.json) | Interim old-baseline comparison: zero mechanical fixes, nine advisory proposals. Compiled-artifact staleness is explicitly reported. No advisory proposal was automatically applied. |
| Final dev build | [14-final-build-verify.json](14-final-build-verify.json) | 17 successful model/seed nodes and 48 passing dbt tests; verification ran with zero findings. |
| Preserve the diff | [15-check-against-original-baseline.json](15-check-against-original-baseline.json) | Intentional staging additions/model changes and three metric-description changes remain observable against the original baseline. |
| Whole-project verification | [16-verify-after.json](16-verify-after.json) | Zero findings and no suppressed axes, with explicit unresolved join/set-operation warnings. |
| Candidate publication path | [18-candidate-build.json](18-candidate-build.json) | The application loaded an isolated candidate, built through Dex, executed every metric, and then replaced the local warehouse. |
| Mutation evidence | [19-snapshot-mutation.json](19-snapshot-mutation.json) | Both generated snapshot-filter defects were caught by `discovery_grid`; no excluded baseline tests or elided mutants. This covers that model and those mutations, not the whole project. |
| Metric execution | [20-metric-execution.json](20-metric-execution.json) | The actual Dex catalog and all 17 MetricFlow query envelopes, including empty results. |
| Fresh map | [21-final-map.json](21-final-map.json) | All 24 objects freshly profiled, none skipped, and zero PII-flagged columns. Inferred keys on single-repository raw data are not multi-repository contracts. |
| Plans | [22-plans.json](22-plans.json) | Engine-generated plan listing and applied/pending states. |
| Baseline acceptance | [23-accepted-baseline.json](23-accepted-baseline.json) | Generated after the verified candidate, numerical integration tests, and refreshed full map. The previous comparison is retained above. |
| Final maintenance | [24-final-check.json](24-final-check.json) | Schema, volume, grain, semantic, and verification results against the accepted state; original findings are retained. |
| Readiness | [25-status.json](25-status.json) | Validated code/input digest, exact traffic coverage, source revision, collection age, and separate freshness status. |
| Discovery diagnostics | [26-discovery-profiles.json](26-discovery-profiles.json), [27-cardinality-diagnostic.json](27-cardinality-diagnostic.json) | Profile evidence and firewalled aggregate probes explain the remaining cardinality notices. |

The root `.dex/cache.json`, `.dex/snapshot.json`, `.dex/drift.json`, and `.dex/plans/` are engine-generated and visible to Git. Review and commit the accepted snapshot like a lockfile. Use `dex transform plans` to inspect plans. `p00d3a022ec` is a superseded, unapplied proposal with unnecessary formatting changes; `p7ae49ddfc3` replaced it. Do not apply the superseded plan.

## What validation does and does not establish

[validation-tests.log](validation-tests.log) records **35 passing integration tests and one skipped live-network test**. These exercise real DuckDB and MetricFlow over two deterministic repositories: counts, ratios, missing observations, rolling snapshots, UTC boundaries, definition drift, failed-build recovery, publication, and plan/apply. [validation-lint.log](validation-lint.log) records passing lint and formatting checks. The publication gate now also rejects a build whose verification response is missing or says it did not run.

Dex cannot automatically resolve the discovery models' list-expansion joins or assign a single driving parent to event unions and the calendar. Those remain warnings; the discovery grid assertion and numerical integration tests provide additional evidence. Zero findings does not mean every relationship was automatically proved.

Final maintenance still reports seven low-severity empty-source notices and two medium-severity dimension-cardinality notices. The latter compare path counts of 69 → 79 and referrer counts of 23 → 22 even immediately after a refreshed baseline. The diagnostic queries on the same unchanged tables return **79 exact versus 69 approximate paths**, and **22 exact versus 23 approximate referrers**. This is consistent with comparing approximate profile counts with exact maintenance counts; it is not evidence that those categories were added or removed during this audit. The original findings remain visible; no cache editing, detection override, or repeated baseline replacement was used to erase them.

The discovery profiles also flag that the warehouse permits nullable grain columns. The dbt `not_null` tests prove their current values are non-null; they do not install physical `NOT NULL` constraints. Read those two claims separately.

Mutation checking of `fct_traffic` failed with a semantic-model validation error ([10-traffic-mutation.json](10-traffic-mutation.json)). Staging traffic has no mutation operator the engine supports ([12-staging-mutation.json](12-staging-mutation.json)). Neither result establishes mutation coverage. The successful, bounded snapshot-model check is reported separately above.

The preferred definition-splicing command refused the existing YAML layout ([09-semantic-definitions-refusal.json](09-semantic-definitions-refusal.json)). Its diagnostic explicitly requested a whole-file edits payload. The accepted semantic plan used that guarded route, and its diff changes only the intended descriptions. Row attribution was not emitted by this engine release; no missing attribution is treated as a zero-row delta.

The real-data candidate is existing public `exmergo/dex` history at Git revision `031e95d61f01fc469c35299f5fa7c1b55e229d5a`. It contains 116 traffic days and 212 raw discovery snapshots. This offline candidate has no supplemental observed star/fork captures or releases: four observed-growth metrics return no rows. Those results establish execution, not data availability. The two-repository fixture suite validates their numerical behavior. Historical data must not be presented as fresh, and no missing source was fabricated.

These audit commands used the former requirements-based bootstrap. The later [native uv migration](uv-migration/README.md) replaces that bootstrap with `uv.lock`, removes the duplicate constraints and requirements lock, and updates commands to `uv run --frozen`. The original command envelopes above remain unchanged as historical evidence.

## Review grouping

Review the staging projections and `models/schema.yml` with model plan `pea618a9ddd`; then review `models/semantic.yml` with semantic plan `p7ae49ddfc3`. Next review `src/oss_analytics/lifecycle.py` and its skipped-verification regression tests. Review the generated artifacts, `.gitignore`, agent instructions, and lifecycle documentation together so the evidence-retention policy is explicit. Git commits remain the maintainer's choice.

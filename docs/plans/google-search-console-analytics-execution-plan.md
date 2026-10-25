# Google Search Console Analytics — execution plan

Status: proposed delivery plan, 2026-10-24. Companion: [grand design](google-search-console-analytics-grand-design.md).

Target repository: `google-search-console-analytics`. Target stack: Google Search Console native export → BigQuery → dbt → MetricFlow → Dex → founder/agent answers.

This plan begins with the export already configured by the maintainer. It also delivers the complete ingestion tutorial for new users. No warehouse inspection or build was performed to write these planning documents. Actual project/dataset names, coverage, budget, and publication-safe example data must be established during execution.

## 1. Delivery rules

1. Start with one verified property and one useful answer. Expand only after that path runs on BigQuery.
2. Use `/dex:explore`, `/dex:transform`, and `/dex:maintain` as agent workflows, backed by recorded engine commands.
3. Inspect actual source columns, grain, values, and coverage before authoring models. Proposed contracts in the design are not an inspected schema.
4. Create all dbt SQL/YAML changes through genuine Transform plans. Read diffs, declarations, warnings, and row attribution where available before applying. Do not hand-edit and manufacture a retrospective no-op plan.
5. Build only against an explicitly configured dev target. Source exports remain read-only to this project.
6. A successful command exit is not sufficient: inspect errors, warnings, verification coverage, suppressed checks, and result truncation.
7. Compare changes against the previous accepted baseline. Preserve that comparison before any deliberate rebaseline.
8. Record exact dependency versions and CLI contracts. Proposed `gsc-analytics` commands below are interfaces to implement, not existing commands.
9. Spend only within a user-authorized policy, preserving Dex's configuration and cost-confirmation contracts.
10. Do not publish private source values, plans, or logs automatically. Build public evidence from explicitly approved data.

## 2. Milestone sequence

| Milestone | Outcome | Depends on | Exit gate |
|---|---|---|---|
| M0 | Inspectable source and compatible pinned stack | Existing export and authorized access | One real governed metric query on BigQuery; cost/refusal behavior understood. |
| M1 | New repository and repeatable setup | M0 | Clean setup connects to the existing export without modifying it. |
| M2 | Correct base models and metrics | M1 | Site and URL contracts pass value tests through MetricFlow; initial baseline accepted. |
| M3 | Founder cookbook and agent answers | M2 | Every P0 question passes numerical, coverage, and refusal tests. |
| M4 | Safe refresh and scheduled checks | M2, M3 | Revised exports, partial builds, and budget limits behave correctly. |
| M5 | Demonstrable Explore → Transform → Maintain lifecycle | M2, M3 | Real customization and isolated regression have complete evidence. |
| M6 | README, tutorial, real examples, and Enterprise CTA | M3–M5 | Fresh-install walkthrough and independent agent walkthrough succeed. |
| M7 | Pilot and launch | M6 | Pilot issues resolved, public evidence reviewed, release checklist complete. |

M0–M3 form the critical path. Documentation can be drafted alongside implementation, but runnable instructions and results are finalized from actual execution.

## 3. M0 — source discovery and compatibility spike

### Inputs to establish

- GCP billing/query project, Search Console export project/dataset, property identifier, and BigQuery location.
- Separate dev dataset and permission to create/modify derived objects there.
- Existing Google authentication; do not ask for secrets in chat.
- An explicit exploration/build budget and session ceiling decision.
- Actual available dates and whether a public example may use this property's values.

Discover non-secret configuration already available before asking the maintainer for missing identifiers. Publishing example data is a separate decision from permission to inspect it privately.

### Work

- [ ] Read the installed Dex skills and pin their version alongside the engine.
- [ ] Identify a compatible set of Dex with `bigquery` and `semantic` support, dbt Core, dbt-bigquery, and MetricFlow. Resolve and lock it; do not assume the DuckDB reference environment works unchanged.
- [ ] Configure the BigQuery connector through `dex config` with an explicit source/dev allowlist. Confirm that dbt and Dex use the same project, location, and dev dataset.
- [ ] Run connection testing and metadata inventory first.
- [ ] Profile/map the actual source tables through Explore within the approved budget. Record expected and unexpected columns, raw repeated-key behavior, search types, anonymity representation, and coverage.
- [ ] Inspect ExportLog using schema-verified read-only Dex probes. Establish per-table dates and how revisions appear.
- [ ] Run a tiny Transform-created dev model and semantic metric through the full path: plan → apply → build/verify → semantic query.
- [ ] Prove that `--local` compiles MetricFlow and executes through Dex's BigQuery connector with spend controls.
- [ ] Exercise dimension discovery, a filtered query, a weighted ratio, and date grouping.
- [ ] Test mover ranking across both periods over more than 50 entities. Decide whether native governed offset metrics suffice or comparison marts are required.
- [ ] Confirm how development build verification, row attribution, mutation testing, and Maintain scan offers behave on this pinned BigQuery version. Record unsupported or skipped operations honestly.
- [ ] Confirm the scheduled authentication path and whether Dex's persisted budget policy supports the intended noninteractive workflow.

Starting engine commands, subject to the version's returned envelopes:

```bash
uv run --frozen dex connect test --connector bigquery
uv run --frozen dex explore inventory --rank
uv run --frozen dex explore map --scope <export_dataset>
uv run --frozen dex explore diagram
```

These examples omit confirmation flags deliberately: inspect the estimate first, then execute with the user's authorized budget in the units returned. Never supply a fictional default ceiling to make the tutorial run.

### Deliverables and gate

- A source-discovery record with exact inspected scope and remaining unknowns.
- A pinned dependency matrix and a working end-to-end command transcript.
- A written ranking decision and measured scan sizes for the smallest useful query.
- A record of actual Dex-generated artifact paths and fields.

**Stop expansion if the governed BigQuery path fails.** Fix or upgrade the compatibility layer and repeat the spike. Do not substitute hand-written reporting SQL or a DuckDB-only demonstration for the promised stack.

## 4. M1 — repository foundation and onboarding

### Work

- [ ] Create the new repository using the agreed name. Keep this GitHub analytics repository as a reference.
- [ ] Bootstrap the dbt skeleton using `dex transform init` with the chosen name and BigQuery connector.
- [ ] Add reproducible dependency setup, lockfiles, lint configuration, license/notices, and contributing instructions.
- [ ] Create the non-secret source/rule configuration schema with validation.
- [ ] Implement bootstrap preflight checks for prerequisites, credentials, location, source visibility, and dev write scope.
- [ ] Keep initial configuration small: project/dataset/location/property/dev target. Brand terms and page groups are optional until their recipes are requested.
- [ ] Define private defaults for runtime evidence; public demo artifacts live under an isolated example path.
- [ ] Write `AGENTS.md` around the read path and engineering path below.
- [ ] Add a template setup checklist for users, without automatically changing their Google Cloud resources.

Proposed repository structure:

```text
README.md
AGENTS.md
pyproject.toml
uv.lock
dbt_project.yml
profiles.yml                  # non-secret settings / credential discovery
sources.example.yml           # config example; final schema decided in M1
models/
  staging/
  intermediate/
  marts/
  semantic/
  time_spine/
seeds/                        # reviewed rules and synthetic fixtures only
src/gsc_analytics/
  status.py
  questions.py
  evidence.py
  lifecycle.py
tests/
  fixtures/
  integration/
scripts/
  bootstrap.sh
docs/
  setup.md
  questions.md
  metrics.md
  architecture.md
  lifecycle.md
  operations.md
examples/
  public-demo/                # approved captured results and demo Dex evidence
.dex/
  config.yml
  cache.json
  snapshot.json
  drift.json
  plans/
  review/
.github/workflows/
  ci.yml
  refresh.yml
```

The `.dex/` entries represent engine-generated state in an initialized project. Do not hand-author them. In the distributable template, keep maintainer-specific maps, baselines, and plans under the example workspace; bootstrap creates the user's own active state.

### Agent answer protocol

1. Read status, source freshness, build validity, and exact recipe coverage.
2. Discover available recipes. Choose the matching one when present.
3. Otherwise discover metrics and their definitions, then dimensions and actual filter values.
4. Execute governed MetricFlow queries through Dex with the approved budget.
5. Inspect the entire envelope: execution backend, warnings, errors, truncation, and metric time axis.
6. Answer with exact scope, periods, values, units, caveats, and provenance.
7. If unavailable, explain why and what will make the answer possible; do not invent zeroes or a shorter period.

Proposed wrapper interface:

```bash
uv run --frozen gsc-analytics status --json
uv run --frozen gsc-analytics questions
uv run --frozen gsc-analytics question weekly-review --property <property>
```

Use the wrapper for orchestration and evidence only. Arithmetic between governed results is allowed; recreating CTR, position, or base counts in Python is not.

### Gate

From a fresh checkout, a user with an existing export reaches a working connection without touching ingestion. Missing credentials or permissions produce a precise next step, and no sensitive configuration is committed.

## 5. M2 — base models, definitions, and correctness

### Transform sequence

Make small reviewable plans in this order:

1. Source declarations, typed staging, source coverage, and time spine.
2. Separate site and URL daily facts, dimensions, and explicit model declarations.
3. Core semantic models and metrics.
4. Brand classification and page groups, with rules and tests.
5. Comparison models/metrics if required by the M0 ranking spike.

For each change:

```bash
uv run --frozen dex transform plan "<specific intended change>" --edits-file <payload>
uv run --frozen dex transform apply <reviewed-plan-id>
uv run --frozen dex transform build --target dev --verify
```

Apply only after reading the returned diffs and warnings. Declare intended grain, population, column roles, and assumptions in the plan. For existing models, obtain authorized row attribution where supported; otherwise record why it was not measured.

After a valid build, discover/query the actual metrics:

```bash
uv run --frozen dex explore semantic list --local
uv run --frozen dex explore semantic values <discovered-dimension> --metric <discovered-metric> --local
uv run --frozen dex explore semantic query <discovered-metrics> --local
```

Concrete README examples must add the discovered property/time filters using MetricFlow's `Dimension` and `TimeDimension` syntax. Do not ship the unrestricted placeholder query above as the production quickstart.

### Required correctness cases

| Fixture / mutation | Required result |
|---|---|
| Several additive raw rows share all selected dimensions | Contributions are summed; `DISTINCT` does not discard real counts. |
| Multiple URLs occur under the same property/query/date | Site totals remain site-based; page metrics remain URL-based; no fact-to-fact fanout. |
| Days have unequal impressions and CTRs | Aggregate CTR equals aggregate clicks / impressions, not mean daily CTR. |
| Different position numerators and uneven impressions | Correct source-specific, weighted, one-based average position. |
| Null and empty anonymous query representations | Counts survive; query text stays unavailable; brand class is unknown. |
| Case variants, overlapping brand terms, and unmatched queries | Deterministic reviewed matching; no accidental substring rule silently changes the population. |
| Overlapping page rules and unusual URLs | First-match group is stable; exact URL identity remains intact; unmatched pages are visible. |
| Zero impressions or zero previous clicks | Null/undefined ratios and explanatory labels; no infinity or invented growth percentage. |
| Missing day, delayed URL export, or stale last export | Affected recipe is unavailable; unaffected historical requests retain honest status. |
| Property/date/search-type filter changed | MetricFlow returns the correct population and source time axis. |
| Time spine fills dates around a source hole | Coverage still blocks invented zero days. |
| Multiple properties or search types in a fixture | No accidental cross-property totals or blending of incompatible search types. |
| More than 50 pages, with a large loser outside either period's top list | Full-population mover ranking finds the loser without relying on truncated period lists. |
| Multiple comparison anchors in a mart | Required anchor filter prevents summing overlapping windows. |

Expected fixture answers should be independently hand-calculated or asserted from tiny known inputs. Use real MetricFlow calls through Dex on an isolated BigQuery dataset for integration tests. Parse-only tests and raw SQL equality checks are insufficient evidence of semantic correctness.

### Baseline gate

- [ ] Core integration/value tests pass.
- [ ] Inspect `transform build --verify` findings, checks run, and suppressions.
- [ ] Run Maintain verification and approve any needed scan budget to exercise the launch-critical axes.
- [ ] Refresh the map for the intended complete scope.
- [ ] Accept and generate the initial snapshot with `dex maintain snapshot`.
- [ ] Commit safe baseline/map evidence and run `dex maintain check` against it.

No previous baseline exists for the first build; use `maintain verify` first. Later phases must retain old-baseline comparisons.

## 6. M3 — executable founder questions

### Work

- [ ] Implement P0 recipes in the design, starting with `export-health` and `search-growth`.
- [ ] Add `nonbrand-growth`, then page movers and selected-page query movers.
- [ ] Add content groups and the explicitly heuristic page-opportunity shortlist.
- [ ] Compose `weekly-review` from the same underlying recipes and anchor policy.
- [ ] Make each recipe publish dependencies, required history, defaults, thresholds, and unavailable reasons.
- [ ] Validate exact-date requests separately from latest-complete-window requests.
- [ ] Store the recipe's governed query specification and returned evidence. Do not make the LLM the only implementation of the question.
- [ ] Make full-population ranking and intentional top-N handling explicit in result metadata.
- [ ] Return absolute changes, relative changes, and percentage-point changes with distinct labels.
- [ ] Add unknown-query and unmatched-page-group coverage to relevant answers.
- [ ] Ensure missing brand rules block only the branded/nonbranded section; the report explains the missing section rather than silently omitting it.

### Answer envelope contract

Each result carries:

- Recipe identifier/version and readiness or an explicit unavailable reason.
- Property, search type, site/URL aggregation scope, groupings, and filters.
- Current and comparison `[start, end)` periods and timezone.
- Governed metric names, definitions references, values, and units.
- Required-source completeness, observed/expected days, holes, and freshness.
- Query-text visibility and classification coverage where applicable.
- `truncated`, top-N intent, total-population/residual evidence, warnings, and missing axes.
- Build ID, source revision-manifest digest, code revision/digest, rules digest, and dependency versions.
- Query/job references and spend when supplied by the engine.

The exact envelope is our wrapper's stable contract; do not depend on undocumented Dex JSON fields without a pinned adapter/test.

### Agent acceptance scenarios

Run each in a fresh agent context using only the proposed repo's instructions:

```text
Did non-branded Google search clicks grow over the last 28 complete days?
Which pages lost the most clicks? Investigate the searches for the biggest loser.
Which of our comparison pages already get impressions but few clicks?
Are our docs or blog pages bringing more search traffic?
Can I trust this week's numbers, or is the export late?
Which search queries brought paying customers?
```

The final question must explain that the required customer/revenue data is absent. The agent must discover metric names, refuse incomplete windows, and avoid reimplementing metrics with ad hoc SQL.

### Gate

All P0 recipes pass fixtures and the approved live export. The agent produces useful, source-grounded answers, including correct refusals. P1 recipes stay out of launch claims until their additional inputs and tests exist.

## 7. M4 — refresh, corrections, CI, and failure behavior

### Work

- [ ] Implement a source revision manifest and coverage checks using the inspected export schema.
- [ ] Start with a bounded full rebuild to establish correctness and measured cost.
- [ ] Add idempotent affected-partition replacement; compare its results with the full rebuild.
- [ ] Detect revisions to dates older than the ordinary refresh lookback and rebuild their dependent comparisons.
- [ ] Detect source revisions during a build; fail validation or retry within the same authorized budget.
- [ ] Mark derived results unavailable before a build and restore readiness only after all required validations pass.
- [ ] Preserve the last validated report as historical if a build partially fails. Do not claim the mutable derived dataset rolled back atomically.
- [ ] Keep Google's source tables intact on all failure paths.
- [ ] Serialize refreshes and baseline operations; record immutable run IDs to prevent one run's evidence from validating another's build.
- [ ] Set up CI with short-lived credentials, isolated test targets, and explicit cost ceilings.
- [ ] Never expose live credentials to untrusted fork PRs. Run credential-free tests there; gate BigQuery integration on trusted contexts.
- [ ] Prove the noninteractive cost contract before enabling an opt-in schedule. Preserve daily/session spend accounting across all commands in the workflow.
- [ ] Persist required private runtime state across ephemeral CI runners without hand-authoring engine internals. Keep the accepted baseline distinct from daily source revision manifests.
- [ ] Run coverage, build verification, semantic integration checks, and Maintain against the accepted baseline.
- [ ] Block validated-report publication on structural/grain errors, changed metric definitions, incomplete required coverage, or required checks not run. Report expected volume movement without automatically treating growth as corruption.
- [ ] Require explicit review for rebaselining. A schedule never snapshots merely to make a check pass.

### Failure drills

Test: one source export late; a missing middle date; a corrected old partition; disappearance of a prior partition; authentication expiry; region mismatch; source column change; altered brand rules; a partial dbt failure; exceeded query budget; concurrent refresh attempt; new data during build; and truncated semantic output.

For each, assert the readiness state, report behavior, recovery instructions, preserved source data, baseline stability, and actual checks performed. Use controlled fixtures/dev copies for destructive simulations.

### Gate

The unattended path either produces validated output under the authorized policy or a clear failure artifact. It never weakens a definition, bypasses a cost guard, replaces the accepted baseline, or emits misleading current metrics to keep a workflow green.

## 8. M5 — show Dex doing real engineering

Create a linked, readable audit trail, following the reference repository's `.dex/review/README.md` pattern.

### Demonstration A: Explore the actual export

- [ ] Capture connection, scoped inventory/map, source grain/coverage findings, and the exact returned diagram.
- [ ] Explain one concrete modeling consequence: site and URL populations must remain separate, or repeated raw keys must be aggregated.
- [ ] Link the discovery evidence to the model declaration that implements the decision.

### Demonstration B: Transform a useful customization

- [ ] Add `/compare/` as a separate page group using a real plan.
- [ ] Record intended precedence, diffs, declarations, and row attribution when measured.
- [ ] Apply and build on dev with verification.
- [ ] Run MetricFlow queries proving URL-group redistribution and unchanged site totals.
- [ ] Maintain against the prior baseline; explain intentional and unexpected findings.
- [ ] Preserve the prior comparison before accepting a refreshed map/snapshot.

### Demonstration C: Detect a real class of mistake

- [ ] In an isolated project, change a metric definition or introduce a grain defect through a test fixture.
- [ ] Show Maintain identifying the change and which outputs become untrustworthy.
- [ ] Request a reconciliation proposal where supported. Distinguish mechanical proposals from advisory decisions.
- [ ] Apply a reviewed repair through Transform, then rebuild and verify.
- [ ] Demonstrate that replacing the baseline is not the repair.

### Evidence checklist

Capture map/cache, accepted snapshot, prior snapshot/comparison, plan IDs and outcomes, configuration diffs, declarations, build/verification envelopes, drift report, semantic query results, available spend evidence, and dbt run artifacts. Store raw envelopes safely; write prose separately. Use synthetic demo artifacts when live outputs cannot be published.

Gate: a reader can follow the actual change from source evidence to definition to tested answer. “Built with Dex” must link to this work.

## 9. M6 — README, setup tutorial, and real answers

### Ingestion tutorial

- [ ] Include both existing-export and new-export routes.
- [ ] Document the Search Console owner/GCP prerequisites, billing, APIs, export principal permissions, dataset naming/location, and enabling bulk export.
- [ ] Separate the five-minute configuration target from data-arrival time and the history needed by comparisons.
- [ ] Link to Google's current instructions; verify UI labels during the walkthrough.
- [ ] Show how to confirm success and troubleshoot missing exports without inferring zero traffic.
- [ ] Check inherited dataset/table/partition expiration settings; explain retained-history implications.
- [ ] Explain why native export cannot supply pre-setup history and defer API backfill explicitly.

Canonical references: [start bulk export](https://support.google.com/webmasters/answer/12917675?hl=en), [monitor exports](https://support.google.com/webmasters/answer/12919198), [table reference](https://support.google.com/webmasters/answer/12917991?hl=en), [query guidance](https://support.google.com/webmasters/answer/12917174?hl=en).

### README examples

- [ ] Run the four stories in the grand design against sufficiently complete, approved real data.
- [ ] Record the exact question, CLI/recipe, property, date ranges, metrics, result, coverage, capture time, source manifest, and code revision.
- [ ] Make the output easy to scan: a short table and one interpretation tied to a founder action.
- [ ] Include a truthful refusal or data-health finding.
- [ ] Keep real captured examples and synthetic fixture examples visibly separate.
- [ ] Freeze approved inputs when claiming replayability; otherwise label outputs as captured at a specific revision/time.
- [ ] Put the first real answer before detailed architecture in the README.

### Agent documentation

- [ ] Show plugin installation for a tested host and the `/dex:explore`, `/dex:transform`, `/dex:maintain` prompts.
- [ ] Provide the equivalent skill/AGENTS.md route for other agents.
- [ ] Make engine commands reproduce the same evidence independently of the agent's prose.
- [ ] Explain `--local`, BigQuery billing, actual metric discovery, filter syntax, row caps, and cost-confirmation handling.
- [ ] Link each README metric and question to its definition/cookbook entry.

### Enterprise CTA

Use the copy from the design after the useful tutorial and lifecycle evidence:

> Want your agents to scale analytics on BigQuery? Talk to us about Dex Enterprise.

Link to [Book a demo](https://www.exmergo.com/book-demo) and [Dex Enterprise](https://www.exmergo.com/dex/enterprise). Verify both destinations before release. Respect the Enterprise page's current availability wording; do not invent a feature list or make Enterprise a prerequisite for this repository.

### Gate

A new user completes the walkthrough without maintainer intervention, and an independent agent answers the cookbook from the repository instructions. Fix undocumented prerequisites before describing setup as low effort.

## 10. M7 — pilot, release, and learning

- [ ] Pilot with a few founders who already have exports; include at least one property unlike the maintainer's.
- [ ] Observe setup, first answer, next weekly review, and one customization. Record where people stall and what they actually inspect afterward.
- [ ] Exercise a new-export onboarding path so the wait-for-data experience is real.
- [ ] Verify no demo baseline, project ID, credentials, private query values, or accidentally published logs remain in the public template's active configuration.
- [ ] Check all links, commands, installed skill versions, dependency pins, licenses, and claimed features.
- [ ] Publish the source and tag a tested release through the normal maintainer workflow.
- [ ] Publish a small launch story centered on one real founder question and its answer, with the repo link.
- [ ] Cross-link from GitHub repo analytics and Dex's real-project examples when authorized.
- [ ] Track voluntary pilot feedback and demo-link interest; do not add hidden usage reporting to the user's warehouse workflow.

Do not expand to more sources until the single-source weekly workflow is useful enough that founders repeat it.

## 11. Release acceptance checklist

- [ ] Name and founder promise match the implemented scope.
- [ ] Existing-export setup preserves the user's working ingestion.
- [ ] New-export tutorial and waiting states are tested.
- [ ] Source schema and grain were explored in the implementation session.
- [ ] SQL/YAML changes were genuinely planned/applied through Dex.
- [ ] BigQuery/dbt/MetricFlow/Dex versions are pinned and exercised together.
- [ ] All P0 recipes run through governed metrics and have numerical tests.
- [ ] Missing coverage, anonymous queries, zero denominators, and source revisions behave correctly.
- [ ] Full-population mover ranking is correct beyond 50 entities.
- [ ] Incremental and full rebuilds agree on corrected data.
- [ ] Dev-only writes and approved cost limits are enforced.
- [ ] Required verification axes ran; skipped axes are disclosed, not passed silently.
- [ ] Accepted baseline and old-baseline comparisons are retained.
- [ ] Actual Dex artifacts support the Explore/Transform/Maintain walkthroughs.
- [ ] Scheduled refresh never auto-rebaselines or publishes invalid fresh answers.
- [ ] README results are approved real outputs with provenance.
- [ ] Another agent can use the repository without bespoke maintainer prompts.
- [ ] Enterprise CTA works and makes accurate availability claims.

## 12. Decisions to settle during execution

| Decision | Default direction | Resolve by |
|---|---|---|
| First live property and public example rights | Use the maintainer's existing export privately; publish only approved evidence. | M0 |
| Exact versions and BigQuery authentication | Pin the smallest proven compatible stack; local ADC and short-lived CI credentials. | M0 |
| Mover ranking implementation | Prefer governed MetricFlow comparisons if they prove correct; otherwise explicit comparison marts. | M0 |
| Spend policy and scheduling feasibility | User-chosen ceilings; scheduled workflow stays disabled until the noninteractive contract is proved. | M0/M4 |
| Initial history materialization | Bounded range with visible coverage; expand deliberately within budget. | M2 |
| Brand rules and path groups | Small explicit configuration, tested precedence, unknown/unmatched buckets. | M2 |
| Private evidence retention and public demo packaging | Keep user runtime evidence private; separate approved example workspace. | M1/M5 |
| Enterprise link/availability wording | Use the real Exmergo destinations and verify current wording before release. | M6 |

These are implementation inputs and acceptance decisions, not reasons to postpone the repository's design. The first execution step is M0: connect to the existing export through Dex and prove one complete, governed founder answer.

# Explore, Transform, Maintain with Dex

The metric definitions and tests are the value of this repository. Dex helps an agent understand, change, and maintain them through reviewable engineering work. Start with a completed README setup and an accepted baseline.

Agents should read the installed skills under `.agents/skills/{explore,transform,maintain}/SKILL.md`. The project-pinned `uv run --frozen dex` commands below invoke the actual Dex engine; the skills also provide a standalone launcher with its own release pin. Inspect each command's envelope, especially refusals, warnings, skipped checks, and attribution when available. Never replace a refused engine operation with hand edits to the project.

The repository's [audit trail](../.dex/review/README.md) records a complete session: exploring new raw tables before writing SQL, three Transform plans (staging, marts, semantic layer) with row attribution and verified dev builds, a Maintain check against the previous baseline, a reconcile proposal that was reviewed and rejected, a metric-definition fix that `check` caught, mutation testing, and the accepted baseline. It also lists the engine limitations met along the way.

## Explore the existing warehouse

```bash
uv run --frozen dex connect test
uv run --frozen dex explore inventory --rank
uv run --frozen dex explore profile analytics.raw.traffic
uv run --frozen dex explore relationships --use-project --verify
uv run --frozen dex explore map --use-project --verify
uv run --frozen dex explore diagram
uv run --frozen dex explore semantic list --metric views --local
```

Inspect the returned grain and candidate-key evidence. The raw traffic grain is repository × date. A per-repository fixture can make another combination look unique by coincidence; the dbt tests and semantic declarations carry the intended contract. `.dex/cache.json` records evidence rather than becoming another place to define business logic.

## Transform a useful dimension

This runnable example adds a `has_page_views` dimension to observed traffic days. It classifies an observed zero-count day as false; it does not fill missing days with zero.

```bash
uv run --frozen python scripts/prepare_lifecycle_example.py
uv run --frozen dex transform plan "Expose whether an observed traffic day has page views" \
  --edits-file .data/tutorial-edits.json
```

The script writes only a proposed edits payload. It contains two entries: `model_sql` for the new expression in `fct_traffic`, and `semantic_yml` for the dimension. Dex validates the allowed file paths, checks the SQL/YAML, shows the diff, and stores a plan under `.dex/plans/`.

Read the plan's `diffs`, warnings, and returned `data.plan_id`. Apply the reviewed ID:

```bash
uv run --frozen dex transform apply <plan-id>
uv run --frozen oss-analytics build
uv run --frozen dex explore semantic query views --local \
  --group-by repository__name,traffic_row__has_page_views
```

A complete command payload follows this shape:

```json
{"edits":[{"path":"models/marts/fct_traffic.sql","kind":"model_sql","op":"upsert","content":"<full SQL model>"},{"path":"models/semantic.yml","kind":"semantic_yml","op":"upsert","content":"<full semantic YAML>"}]}
```

An agent can prepare a different payload for the maintainer's actual request. Shared-file metric updates can also use Dex's `semantic plan --definitions-file` payloads to preserve unrelated content; for this repository's `models/semantic.yml` layout the splicer refuses and asks for a whole-file `--edits-file`, which is the guarded route to take. Never edit generated manifests to change a definition.

`dex transform test --mutate <model>` measures whether tests catch planted defects. It works on models outside the semantic layer (for example `fct_snapshot_status`); the 1.15 engine cannot mutate a model that backs a semantic model, so those are covered by value tests in `tests/test_metrics.py`.

`oss-analytics build` loads a candidate warehouse and uses Dex's `transform build --target dev --verify`. It then profiles the candidate and exercises real MetricFlow queries before replacing the local database. A successful dbt parse alone is insufficient.

## Maintain against the previous accepted state

```bash
uv run --frozen dex maintain check
uv run --frozen dex maintain schema
uv run --frozen dex maintain grain
uv run --frozen dex maintain semantic
uv run --frozen dex maintain verify
```

Review findings, impacted metrics, axes run, warnings, and skipped checks. The intended dimension is a legitimate schema/semantic change; unexpected source-type changes or duplicate fact keys require investigation. `oss-analytics check` blocks high-severity structural/grain findings and all semantic definition drift while reporting volume anomalies.

Use `uv run --frozen dex maintain reconcile` to obtain proposed repairs for supported drift classes. Inspect its diffs and plan before applying with `dex transform apply`. Reconciliation does not make a new metric definition authoritative merely because the source changed.

After reviewing and accepting the intended new state:

```bash
uv run --frozen oss-analytics baseline
uv run --frozen oss-analytics check
```

Commit the source SQL/YAML edits through your normal review process. The scheduled publication retains the generated baseline and map on the data branch; new agents can recover that evidence. Do not refresh a baseline simply to conceal an unexplained failure.

Review and commit `.dex/snapshot.json` like a lockfile, along with the plan and evidence for an intentional change. Keep the comparison against the previous baseline. `.dex/cache.json`, `.dex/drift.json`, `.dex/plans/`, and `.dex/review/` are visible to Git; local query ledgers and warehouse files are ignored. Use `dex transform plans` to list plans, rather than treating their internal JSON format as a command interface.

## Deliberate regression checks

The integration suite changes a metric expression, rebuilds, and verifies that maintenance detects the definition drift. It also exercises a failed raw load and checks that the prior DuckDB file remains intact. Run `uv run --frozen pytest tests/test_lifecycle.py -q` to reproduce those scenarios in isolated workspaces.

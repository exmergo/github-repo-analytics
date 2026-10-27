# Architecture and provenance

The default branch owns source configuration, SQL, tests, annotations, and semantic definitions. The `github-repo-stats` branch owns raw collected history, supplemental observations, upstream provenance records, `published.json`, and validated Dex state under `analytics-state/`.

Local `.data/inputs/<id>/` directories are immutable imported candidates. Imports list only each configured repository's subtree of the data branch and download files through a content-addressed cache (`.data/blobs/`, keyed and verified by Git blob SHA), so a growing branch is not re-downloaded on every sync. The sync manifest records every resolved Git commit and file checksum. Downloads use raw-content URLs at that commit. Required schema/type errors reject the candidate without replacing the previous sync manifest. Existing local supplemental observations survive future syncs.

The Python loader writes typed `raw.*` tables in a new candidate warehouse. dbt staging views preserve the source contract; dbt marts own grains and derived columns:

| Relation | Grain |
|---|---|
| `dim_repository` | Repository name; `repository_identity` is `github:<id>` when available, otherwise `name:<owner/repo>` |
| `fct_traffic` | Repository × UTC date |
| `fct_observations` | Repository × UTC capture date, latest capture on that date |
| `fct_legacy` | Repository × upstream historical date |
| `fct_snapshot_status` | Repository × endpoint × UTC capture date |
| `fct_referrer`, `fct_path` | Repository × daily snapshot × item ever seen in that endpoint |
| `dim_event` | Repository × stable release/annotation event ID |
| `fct_star_history`, `fct_fork_history` | Repository × covered UTC day (dense; zero only inside coverage) |
| `fct_issues` | Repository × issue or pull request number |
| `fct_release_downloads` | Repository × release asset × UTC capture date, latest capture on that date |
| `fct_package_downloads` | Repository × registry × package × reported UTC day |
| `metricflow_time_spine` | Continuous UTC date |

Facts have unique keys and repository relationships. MetricFlow joins facts through declared entities rather than joining daily traffic directly to many referrers or events. Non-additive time dimensions select the latest observed totals/snapshots within each repository and bucket.

`oss-analytics build` creates an isolated candidate project, loads its raw tables, builds through Dex, checks verification findings, profiles the candidate, and executes every metric through local MetricFlow. It swaps the final DuckDB file only after those checks succeed. Compilation artifacts and cache are copied back; a failed candidate retains the prior database.

`oss-analytics check` executes the semantic smoke suite and Dex's schema, volume, grain, semantic, and verification checks against the previous baseline. It records the current code/input digest. High-severity structural/grain findings and all semantic definition drift block promotion. Volume anomalies are reported for review. Known nullable fields are accepted only when source coverage proves their absence is expected (for example, no consecutive captures for net growth). The original Dex findings and these explanations remain in the check record. A changed code digest makes agent recipes unready until checked again.

CI first persists raw input commits. Validation then pins one candidate commit across all configured projects. A successful publication records that data commit, the code commit, dependency-lock hash, validation time, source records, and tested metrics. It retains cache/snapshot artifacts with the publication. A failure leaves the previous `published.json` intact; readers of a template-managed branch continue using its last approved data commit.

Local artifacts:

- `.dex/config.yml`: committed non-secret connector/project configuration.
- `.dex/cache.json`: generated exploration evidence, visible to Git for review.
- `.dex/snapshot.json`: the accepted project definitions; commit it like a lockfile, in the same pull request as the models and metrics it accepts. The data branch keeps the separate published baseline (`analytics-state/snapshot.json`), the last validated warehouse state. CI combines the two; see [the committed and published baselines](lifecycle.md#the-committed-and-published-baselines).
- `.dex/drift.json`, `.dex/plans/`: generated drift evidence and reviewable change plans, visible to Git.
- `.dex/review/`: saved command envelopes and the audit index; includes limitations and superseded/refused attempts.
- `.dex/*.jsonl`: local query ledgers, ignored.
- `.data/build.json`, `.data/check.json`: validation and provenance records.
- `warehouse/analytics.duckdb`: local materialization, never committed.

Delete the warehouse/cache and rebuild from pinned raw inputs and repository definitions. Keep the accepted baseline when evaluating drift; deleting it intentionally removes that comparison reference.

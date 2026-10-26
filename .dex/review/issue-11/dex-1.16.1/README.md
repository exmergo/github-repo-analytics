# Dex 1.16.1 runtime alignment and revalidation

The branch's setup commit updated installed skills to 1.16.1. The initial issue implementation left the package and lockfile at 1.15.2; that mismatch was an agent oversight. `pyproject.toml` now pins `exmergo-dex-core[duckdb,semantic]==1.16.1`, and the regenerated lock installs that exact version. Its required dependency changes include MetricFlow 0.213.0, certifi 2026.10.23 and urllib3 2.8.0. The SQL and metric definitions have not changed in this follow-up.

The implementation commit is amended to end with `Co-authored-by: Dex <dex@exmergo.com>`, verified directly from the installed engine's canonical attribution constant ([identity evidence](12-runtime-and-attribution.json)). The commit contains the actual SQL/YAML previously written by Dex. No retrospective or no-op Transform plan was created to obtain a trailer. The user's setup commit remains unchanged.

## Validation

- [Full suite](validation-tests.log): **71 passed, 1 opt-in live test skipped** on the new runtime. [Ruff lint and format checks](validation-lint.log) pass.
- [Verified dev build](03-verified-build.json): verification ran, zero findings. Its `no_relation` suppression says dbt run results are authoritative for nodes built; it is retained in the envelope.
- [Comparison with the 1.15.2 baseline](04-check-old-baseline.json): all 41 metrics executed and all four Maintain axes ran. There is no model or metric-definition drift. Warnings identify the older engine baseline; it was preserved in [previous-baseline.json](previous-baseline.json).
- [Full refreshed map](08-final-full-map.json), [accepted snapshot](09-accepted-baseline.json), [final check](10-final-check.json), [status](11-final-status.json): the baseline now records 1.16.1, all four axes ran again, and status is ready. Existing approximate/exact cardinality notices and empty optional sources remain visible. Source collection timestamps were not refreshed by this runtime upgrade; freshness is reported separately in status.
- [Reference usage](05-reference-usage.json): the installed skill's `--usage` workflow now runs on the pinned engine.

## Mutation support and remaining test limits

The 1.15.2 semantic-backed mutation error in the parent audit is historical. Dex 1.16.1 supports this workflow by excluding the referencing semantic model from its shadow project and reports that restriction in warnings.

The [unconfigured live mart](06-mutation-empty-live-model.json) contains no deployment rows: all seven mutants produce the same empty output, so its score of 0 is not evidence that a new assertion on that dataset would help. The [populated fixture run](07-mutation-populated-fixture.json) generated seven mutants, killed one and retained six, with no baseline tests excluded and none elided by the cap. Its score is 1/7; this describes the dbt test set, not the Python/MetricFlow value suite.

Three distinguishable survivors invert the hours calculation, the first-shipping filter or the merge-before-success predicate. Existing MetricFlow integration assertions pin the correct counts and lead-time values, but those Python tests are outside Dex's mutation harness. The remaining equivalent survivors concern a zero-hour boundary, changing an inner join to a left join whose nulls are still filtered, and removing the merge-before-success predicate from fixture data that already satisfies it. Dex recommends fixture-backed unit tests for those cases; the exact defects, equivalence classifications and suggested tests are retained in the envelopes. This revalidation does not claim full dbt mutation coverage.

All JSON evidence is produced by the actual commands, with only local paths normalized. Runtime identity metadata is an explicit inspection of the installed package, not a fabricated apply response. The earlier 1.15.2 artifacts remain intact for historical comparison.

# Metric contract

All timestamps and calendar dates are UTC. Weeks begin Monday. Queries distinguish absent observations from explicit observed zeros. `models/semantic.yml` is the executable definition; this page explains its interpretation.

| Metric | Aggregation | Meaning |
|---|---|---|
| `views`, `clones` | Sum across days/repositories | GitHub page views/full clones, including whatever automation GitHub counted |
| `visitor_days`, `cloner_days` | Sum daily unique counts | Unique observations per day and project; not distinct people across a period |
| `observed_traffic_days` | Count repository-days | Coverage; compare with the requested date count × repository count |
| `views_per_visitor_day`, `clones_per_cloner_day` | Ratio of sums | Intensity; zero denominator returns null |
| `stars_observed`, `forks_observed` | Last observation per repository/time bucket | Actual repository totals observed since supplemental collection began |
| `stars_net_change`, `forks_net_change` | Sum valid consecutive-date changes | Negative values allowed; initial observations and changes across missing dates are null |
| `legacy_stars_cumulative`, `legacy_forks_cumulative` | Last reconstructed value per bucket | Upstream historical series at the pinned revision; not exact historical observed totals |
| `referrer_views_14d`, `path_views_14d` | Latest snapshot per repository/time bucket | Reported counts in one rolling window; never sum overlapping snapshots |
| `referrer_visitor_observations_14d`, `path_visitor_observations_14d` | Latest snapshot per bucket | Reported unique observations; no deduplication across items/repositories |

Every metric supports `repository__name`; time-dependent metrics support `metric_time`. Referrer and path metrics additionally support `referrer_row__referrer` and `path_row__path`. Discover the complete supported groupings through Dex instead of constructing arbitrary fact joins.

## Traffic and coverage

Traffic dates must be unique UTC midnights, counts must be non-negative integers, and uniques cannot exceed totals. The loader imports the upstream aggregate once at its pinned revision. It does not append old copies as new observations or replace upstream aggregation with a different algorithm.

Question recipes exclude the two most recent UTC dates as a conservative recent-data policy. They compare exact 7-day or 28-day calendar windows. Any missing date makes a comparison unavailable; a zero-count observed date remains valid. Direct MetricFlow queries expose data exactly as stored, so callers must apply the same coverage policy where appropriate.

A 28-day sum of `visitor_days` is a count of visitor-days. It cannot answer "How many distinct people visited this month?" Cross-project sums also count the same person's activity independently.

## Star and fork history

Public repository totals are captured when the collector runs. A capture at 04:25 UTC is an observation at that time, not an end-of-day balance. Multiple captures on a day use the latest. A change between consecutive UTC dates is labeled observed net change, not an exact 24-hour event count. Gaps remain visible through `observation_gap_days`.

A new installation has no observed history yet. The upstream reconstructed series remains available under `legacy_*` names, with source revisions. It can change when stars/forks disappear or when upstream collection reaches its historical limits. Never splice it into observed net growth. Missing star/fork files remain unavailable; they do not become a zero series.

## Rolling discovery snapshots

GitHub provides the reported top 10 referrers and paths for a rolling window. The `14d` suffix describes the source's window; it does not mean the repository has a daily attribution feed. Capture timestamps preserve when the report was observed. Rows in these endpoints have no exact individual visit timestamps.

The model retains every raw snapshot and exposes the latest successful capture for each UTC date and endpoint. A dense item grid gives previously reported items explicit nulls when they fall out of the top 10. This lets MetricFlow select the latest date without resurrecting an older category. An empty successful snapshot clears all reported items; a missing snapshot never does.

Historical recipes require exact snapshot dates, report actual capture times, and flag windows captured less than fourteen days apart as overlapping. They compare counts/ranks without adding them. A referrer absent from either window has no numeric change estimate. Ranking means rank among reported items, not a complete census of all traffic sources.

Avoid pre-filtering `is_reported = true` in an unbounded latest-period query: filtering rows before selecting time can reintroduce an older observation. Use exact snapshot-date recipes, or query all rows and interpret null counts after snapshot selection.

## Events and limits

Release/campaign recipes compare `[event date - 7 days, event date)` with `[event date + 1 day, event date + 8 days)`. The event day is excluded. Incomplete windows remain pending, and other events in that range are disclosed. Percentage change is null when the earlier value is zero.

These comparisons show association. None of these sources establish active users, installations, package downloads, user conversion, revenue, bot-free audience size, or causal campaign effects.

# Metric contract

All timestamps and calendar dates are UTC. Weeks begin Monday. Queries distinguish absent observations from explicit observed zeros. The YAML under `models/` contains the executable definitions; this page explains its interpretation.

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
| `views_28d` | Rolling 28-day sum, value at the end of each period | Trailing views; requires `metric_time` |
| `views_wow_growth`, `stars_gained_wow_growth` | Derived, offset by one week | `(this week − last week) / last week`; query at week grain; partial weeks distort it |
| `stars_gained`, `forks_created` | Sum of covered days | Current stargazers by the day they starred; existing forks by creation day |
| `stars_from_history` | Running total, value at the end of each period | Current stargazers through the period end |
| `watchers_observed`, `open_issues_and_prs_observed` | Last observation per repository/time bucket | GitHub watcher count; `open_issues_count`, which includes open pull requests |
| `legacy_stars_change`, `legacy_forks_change` | Sum of reconstructed changes | Upstream historical balance changes; first row null |
| `issues_opened`, `prs_opened` | Count by creation date | Issues exclude pull requests |
| `issues_closed` | Count by close date | Issues only |
| `prs_merged` | Count by merge date | Merged pull requests |
| `first_time_contributor_prs` | Count by creation date | Pull requests GitHub marked first-time-contributor when first collected |
| `median_hours_to_merge` | Median over merged pull requests, by merge date | Hours from opening to merge |
| `release_downloads` | Last capture per repository/time bucket, summed over assets | Cumulative GitHub release asset downloads |
| `release_downloads_net_change` | Sum valid consecutive-date changes | Asset downloads between consecutive daily captures; gaps are null |
| `package_downloads`, `pypi_downloads`, `npm_downloads` | Sum of reported days | Registry downloads for configured packages |
| `deployments` | Sum deployment IDs by UTC success date | Successful non-transient deployments in the configured production environment; redeployments count |
| `median_hours_lead_time` | Continuous median across shipped PRs by deployment date | Hours from merge to the first observed successful deployment containing the merge SHA |
| `events` | Count | Releases and annotations dated in the period |

Every metric supports `repository__name`; time-dependent metrics support `metric_time`. Referrer and path metrics additionally support `referrer_row__referrer` and `path_row__path`. Release metrics and `events` support `event__title`, `event__kind`, and `event__prerelease`. Package metrics support `package_download__registry` and `package_download__package`. Issue metrics support `issue__kind` and `issue__author_association`. Discover the complete supported groupings through Dex instead of constructing arbitrary fact joins.

## Traffic and coverage

Traffic dates must be unique UTC midnights, counts must be non-negative integers, and uniques cannot exceed totals. The loader imports the upstream aggregate once at its pinned revision. It does not append old copies as new observations or replace upstream aggregation with a different algorithm.

Question recipes exclude the two most recent UTC dates as a conservative recent-data policy. They compare exact 7-day or 28-day calendar windows. Any missing date makes a comparison unavailable; a zero-count observed date remains valid. Direct MetricFlow queries expose data exactly as stored, so callers must apply the same coverage policy where appropriate.

A 28-day sum of `visitor_days` is a count of visitor-days. It cannot answer "How many distinct people visited this month?" Cross-project sums also count the same person's activity independently.

## Star and fork history

Public repository totals are captured when the collector runs. A capture at 04:25 UTC is an observation at that time, not an end-of-day balance. Multiple captures on a day use the latest. A change between consecutive UTC dates is labeled observed net change, not an exact 24-hour event count. Gaps remain visible through `observation_gap_days`.

A new installation has no observed history yet. The upstream reconstructed series remains available under `legacy_*` names, with source revisions. It can change when stars/forks disappear or when upstream collection reaches its historical limits. Never splice it into observed net growth. Missing star/fork files remain unavailable; they do not become a zero series.

## Star history from stargazers

`stars_gained` dates each star by when a *current* stargazer starred. People who later unstarred are invisible, so past totals in `stars_from_history` can be lower than what was observed at the time, and `stars_gained` never goes negative. Use it for "when did attention arrive", and `stars_observed` for "what is the total now". The capture day is partial and excluded; days inside coverage with no stars are explicit zeros. GitHub lists at most about 40,000 stargazers; beyond that the listing is marked incomplete and history stops at the cut-off. Forks follow the same rules: deleted forks are invisible.

## Issues, pull requests, and contributors

Counts are dated by the event they measure: opened by creation date, closed by close date, merged by merge date. `issues_*` excludes pull requests. No titles, bodies, labels, or author identities are stored.

GitHub recomputes `author_association` over time: a first-time contributor's pull request reads `CONTRIBUTOR` once merged. Collection keeps the association it first observed, so `first_time_contributor_prs` is accurate from the start of daily collection; backfilled history undercounts. It counts pull requests, not distinct people.

## Downloads

`release_downloads` is GitHub's cumulative `download_count` for uploaded release assets. GitHub does not count source archive (zip/tarball) downloads, so a project without uploaded assets has no release download data rather than zero. These metrics are verified against fixture values only: neither bundled example uploads release assets. Neither release nor registry downloads are users or installations: they include CI, mirrors (npm), bots, and repeated installs.

`pypi_downloads` comes from pypistats.org without mirrors, and `npm_downloads` from the npm downloads API. Registries revise recent days; the newest response wins for each date. Packages are an optional add-on: an unconfigured registry is unavailable, not zero.

## Rolling discovery snapshots

GitHub provides the reported top 10 referrers and paths for a rolling window. The `14d` suffix describes the source's window; it does not mean the repository has a daily attribution feed. Capture timestamps preserve when the report was observed. Rows in these endpoints have no exact individual visit timestamps.

The model retains every raw snapshot and exposes the latest successful capture for each UTC date and endpoint. A dense item grid gives previously reported items explicit nulls when they fall out of the top 10. This lets MetricFlow select the latest date without resurrecting an older category. An empty successful snapshot clears all reported items; a missing snapshot never does.

Historical recipes require exact snapshot dates, report actual capture times, and flag windows captured less than fourteen days apart as overlapping. They compare counts/ranks without adding them. A referrer absent from either window has no numeric change estimate. Ranking means rank among reported items, not a complete census of all traffic sources.

Avoid pre-filtering `is_reported = true` in an unbounded latest-period query: filtering rows before selecting time can reintroduce an older observation. Use exact snapshot-date recipes, or query all rows and interpret null counts after snapshot selection.

## Events and limits

Release/campaign recipes compare `[event date - N days, event date)` with `[event date + 1 day, event date + N + 1 days)` for N = 7 or 28. The event day is excluded. Incomplete windows remain pending, and other events in that range are disclosed. Percentage change is null when the earlier value is zero.

These comparisons show association. None of these sources establish active users, installations, user conversion, revenue, bot-free audience size, contributor sentiment, or causal campaign effects. Downloads are available only for uploaded release assets and configured PyPI/npm packages.

## Production deployments and lead time

These metrics require the opt-in [GitHub deployment source](setup.md#track-production-deployments-optional). `deployments` counts successful deployment IDs by UTC success date, including redeployments with no new PRs. `median_hours_lead_time` uses a separate one-row-per-shipped-PR fact: merge-to-success hours assigned to the earliest observed containing deployment. A deployment shipping multiple PRs still counts once, and redeployments cannot ship the same PR twice for lead time. The median is computed over individual PRs for the requested bucket, never averaged from daily medians. It is measured in hours; it does not include pre-merge development time.

Both metrics use shipping date for `metric_time` and exclude the capture UTC day. Repository keys are included in deployment and PR grains. A missing capture means unavailable. A successful deployment with no mapped PRs can supply a count while its lead-time median stays null. No deployment rows in a window remain absent evidence, never an inferred zero series. Incomplete API listings, old status retention and deleted records limit historical completeness; observed lead time can overstate actual time if an earlier deployment was never observed. This implements two shipping indicators associated with DORA; it does not measure change failure rate or recovery time.

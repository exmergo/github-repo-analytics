# Questions for maintainers and agents

Use `uv run --frozen oss-analytics questions` to list recipes. Each answer contains the executed Dex/MetricFlow envelopes and provenance/coverage evidence. Arguments are passed through validated date windows and escaped MetricFlow filters. Dates below are examples: replace them with dates available in `status`/`events`.

All commands begin with `uv run --frozen oss-analytics question`. Add `--repository exmergo/dex` or another configured project.

| Recipe | Example arguments | Returned evidence and preconditions |
|---|---|---|
| `traffic` | `--start 2026-07-01 --end 2026-07-08` | `views`, `clones`; all seven dates observed and outside the recent-data exclusion |
| `traffic-trend` | `--start 2026-07-01 --end 2026-07-29 --grain week` | `views`, `clones` per day/week/month; full requested coverage |
| `audience` | `--start 2026-07-01 --end 2026-07-29` | `visitor_days`, `cloner_days`; explicitly not unique people over the period |
| `engagement` | `--end 2026-07-29 --days 28` | `views_per_visitor_day`, `clones_per_cloner_day` in two consecutive complete windows; ratios of sums |
| `growth` | `--end 2026-07-29 --days 7` | Two consecutive complete seven-day windows, absolute/percentage change; `--days 28` for four-week comparisons |
| `stars` | `--start 2026-07-01 --end 2026-07-29` | Last observed `stars_observed`, `forks_observed` within the period; needs supplemental captures |
| `star-growth` | `--start 2026-07-01 --end 2026-07-29` | Daily observed net changes; first captures and gaps are null |
| `legacy-growth` | `--start 2026-07-01 --end 2026-07-29 --grain month` | Upstream reconstructed star/fork totals per period, labeled with its source revision |
| `star-history` | `--days 91 --grain week` | `stars_gained`, `forks_created`, `stars_from_history` per period from current stargazers; ends at the last complete day |
| `community` | `--days 28`, or `--start … --end … --grain month` | Issues opened/closed, PRs opened/merged, first-time-contributor PRs, median hours to merge |
| `release-downloads` | No extra arguments | Latest cumulative downloads per release; unavailable when no assets are uploaded |
| `package-downloads` | `--days 28 --grain week` | PyPI/npm downloads per package; unavailable when no packages are configured |
| `compare` | `--days 28` (no `--repository`) | Views, clones, visitor-days, stars gained, PRs merged, package downloads for every tracked repository, with per-repository coverage |
| `referrer-trend` | No extra arguments, or `--start … --end …` | The latest reported top 10, followed back through one latest snapshot per 7-day window |
| `weekly-report` | No extra arguments | Traffic growth, star history, community, release and package downloads; each section states its own window or why it is unavailable |
| `referrers` | `--snapshot-date 2026-07-02` | Referrer, reported views/unique observations; exact successful snapshot required |
| `paths` | `--snapshot-date 2026-07-02` | Popular path, reported views/unique observations; exact successful snapshot required |
| `referrer-change` | `--snapshot-date 2026-07-02 --compare-date 2026-07-16` | Two reported-source snapshots, actual capture times, overlap flag; missing top-10 entries remain unreported |
| `path-change` | `--snapshot-date 2026-07-02 --compare-date 2026-07-16` | Two reported-content snapshots with the same limitations |
| `event-impact` | `--event-id exmergo/dex:release:12345 --days 28` | Views/clones in 7 or 28 complete days before and after, event day excluded; other events disclosed |
| `active-users` | No extra arguments | Explicitly unavailable: the necessary product-usage source is absent |

Star history, community, and package recipes default to the last `--days` days ending at that signal's own last complete day (never "today"), and refuse a window that runs past it. Inside covered windows, a null count means no activity.

Dex returns at most 50 rows per semantic query. Choose a coarser `--grain` or a shorter window for long series; recipes refuse a truncated result rather than presenting part of it.

When a traffic period is omitted, the recipe uses the last available eligible seven-day window. It discloses the actual dates and source age; an old dataset does not become current merely because it was queried today. For growth, use `--end` and `--days`; its start is determined by the consecutive-window rule.

Inspect available events:

```bash
uv run --frozen oss-analytics events
```

For historical snapshot dates and capture times, use the status output for the latest snapshot or Dex's governed inspection surface:

```bash
uv run --frozen dex explore query \
  "select repository, endpoint, date, captured_at from analytics.main.fct_snapshot_status order by date desc"
```

This is snapshot metadata, not a second way to calculate metrics. Every count in a recipe is queried through MetricFlow. Example direct metric query:

```bash
uv run --frozen dex explore semantic query views,clones --local \
  --group-by repository__name,metric_time --grain week \
  --where "{{ Dimension('repository__name') }} = 'exmergo/dex'"
```

Direct queries are useful for exploration. Apply the [metric contract](metrics.md) and check coverage before presenting an answer. Do not add referrer snapshots to estimate visits, interpret a missing top-10 row as zero, or call a traffic ratio a conversion rate.

A useful agent response names the period, count and units, metric identifiers, coverage and freshness, source revision, and current code digest. Snapshot responses also name capture times and rolling-window overlap. State uncertainty in the answer itself rather than dropping it from a final summary.

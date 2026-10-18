# Questions for maintainers and agents

Use `uv run --frozen oss-analytics questions` to list recipes. Each answer contains the executed Dex/MetricFlow envelopes and provenance/coverage evidence. Arguments are passed through validated date windows and escaped MetricFlow filters. Dates below are examples: replace them with dates available in `status`/`events`.

All commands begin with `uv run --frozen oss-analytics question`. Add `--repository exmergo/dex` or another configured project.

| Recipe | Example arguments | Returned evidence and preconditions |
|---|---|---|
| `traffic` | `--start 2026-07-01 --end 2026-07-08` | `views`, `clones`; all seven dates observed and outside the recent-data exclusion |
| `traffic-trend` | `--start 2026-07-01 --end 2026-07-29` | Daily `metric_time__day`, `views`, `clones`; full requested coverage |
| `audience` | `--start 2026-07-01 --end 2026-07-29` | `visitor_days`, `cloner_days`; explicitly not unique people over the period |
| `engagement` | `--start 2026-07-01 --end 2026-07-29` | `views_per_visitor_day`, `clones_per_cloner_day`; ratios of sums |
| `growth` | `--end 2026-07-29 --days 7` | Two consecutive complete seven-day windows, absolute/percentage change; `--days 28` for four-week comparisons |
| `stars` | `--start 2026-07-01 --end 2026-07-29` | Last observed `stars_observed`, `forks_observed` within the period; needs supplemental captures |
| `star-growth` | `--start 2026-07-01 --end 2026-07-29` | Daily observed net changes; first captures and gaps are null |
| `legacy-growth` | `--start 2026-07-01 --end 2026-07-29` | Upstream reconstructed cumulative star/fork evidence, labeled with its source revision |
| `referrers` | `--snapshot-date 2026-07-02` | Referrer, reported views/unique observations; exact successful snapshot required |
| `paths` | `--snapshot-date 2026-07-02` | Popular path, reported views/unique observations; exact successful snapshot required |
| `referrer-change` | `--snapshot-date 2026-07-02 --compare-date 2026-07-16` | Two reported-source snapshots, actual capture times, overlap flag; missing top-10 entries remain unreported |
| `path-change` | `--snapshot-date 2026-07-02 --compare-date 2026-07-16` | Two reported-content snapshots with the same limitations |
| `event-impact` | `--event-id exmergo/dex:release:12345` | Views/clones in seven days before and seven days after, event day excluded; other events disclosed |
| `active-users` | No extra arguments | Explicitly unavailable: the necessary product-usage source is absent |

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

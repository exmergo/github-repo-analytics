# Answering and maintaining this analytics repository

This repository is the source of truth for GitHub growth and discovery analytics. Use the tested MetricFlow definitions through Dex. The Python package orchestrates collection and lifecycle checks; it does not replace MetricFlow.

## Answering a question

1. Run `uv run --frozen oss-analytics status --json`. If `ready` is false, follow the reason before presenting metric results. Read freshness, traffic lag, and exact coverage separately.
2. Use `uv run --frozen oss-analytics questions` and prefer an executable `question` recipe where available. Missing data makes a recipe unavailable; report the reason rather than inventing a smaller comparison window.
3. For other supported questions, discover metrics with `uv run --frozen dex explore semantic list --local` and dimensions with `dex explore semantic values <dimension> --metric <metric> --local`. Never guess metric or dimension names.
4. Query with `uv run --frozen dex explore semantic query <metrics> --local`. Use `repository__name` to select/group repositories and `metric_time` for time. Filters use MetricFlow's `Dimension` and `TimeDimension` syntax. Inspect `truncated`, warnings, errors, and the metric's time axis.
5. Include the repository, exact period (end exclusive), metric names, value, units, freshness/coverage, source revision, and code digest from status. For snapshot answers also include capture times and whether windows overlap. Label historical answers as historical when current data are stale.

Comparison arithmetic on returned governed metrics is allowed. Do not recreate metric definitions with ad hoc SQL, read upstream reports as authoritative answers, sum rolling snapshots, or silently replace absent evidence with zero. The question recipes are the executable reference for these rules.

## Interpretation

- Views/clones may include automation; clones are neither installations nor active users.
- `visitor_days`/`cloner_days` sum daily unique observations. They are not distinct people over a period or across projects.
- `stars_observed`/`forks_observed` select the last capture, including decreases. Initial captures and gaps do not establish daily net change.
- `legacy_*_cumulative` are upstream historical reconstructions at one source revision. They are separate from observed repository totals.
- Referrer/path metrics describe one reported rolling top-10 window. Null indicates unreported. Period grouping selects the latest snapshot; it does not sum windows.
- Never filter `is_reported` before selecting the latest time bucket: that can select an older reported observation. Exact-date recipes already handle unreported items.
- Event comparisons show association. Disclose other events and incomplete windows.
- `stars_gained`/`stars_from_history` date current stargazers by when they starred. Unstars and deleted forks are invisible, so past totals are lower bounds; use `stars_observed` for the current total. Coverage ends the day before capture; `signals.*.complete` false means GitHub truncated the listing.
- Issue metrics count events by their own date (opened, closed, merged). `first_time_contributor_prs` counts pull requests, not people, and undercounts history from before daily collection began. `open_issues_and_prs_observed` includes open pull requests.
- Downloads exist only for uploaded release assets (`release_downloads`, a cumulative balance) and configured packages (`pypi_downloads`, `npm_downloads`). They are not users or installations. A repository without assets or packages is unavailable, not zero.
- Windowed and offset metrics (`views_28d`, `*_wow_growth`) need `metric_time`; partial first/current weeks distort week-over-week growth. Dex returns at most 50 rows per semantic query: choose a coarser grain rather than reading a truncated result.
- If asked for active users, installations, conversion rates, contributor sentiment, or revenue, state that the required source is absent.

## Build and maintain

Bootstrap with `bash scripts/bootstrap.sh`. Initial setup is `sync`, `build`, `baseline`, `check`. Later updates are `sync`, `build`, `check`; review findings before explicitly refreshing the baseline. Never automatically replace a baseline to make a failed check pass.

Read the installed skills in `.agents/skills/explore/SKILL.md`, `.agents/skills/transform/SKILL.md`, and `.agents/skills/maintain/SKILL.md` before analytics engineering. Explore the data in this session; create a reviewable Transform plan for SQL/YAML edits; read its diffs, warnings, and row attribution when available; apply, build, and verify; then Maintain against the previous baseline. Do not substitute hand edits or retrospective no-op plans for that workflow. See docs/lifecycle.md for edits payloads and commands. Dex is read-only against existing warehouse data outside its dev build lifecycle. Python ingestion owns raw-table writes.

After changing models or definitions, run the integration tests, build and check. Tests exercise MetricFlow against DuckDB; a YAML parse or dbt build alone does not establish metric correctness. Inspect Dex findings and skipped axes even when the command exits successfully.

Do not hand-author `.dex/cache.json`, `.dex/snapshot.json`, or `.dex/plans/` contents. Change Dex configuration through `dex config`, following its confirmation contract. Maps, plans, drift reports, and the accepted baseline are visible to Git; review and commit the accepted snapshot like a lockfile. Keep the old-baseline comparison when accepting an intentional change. CI also preserves validated state on the data branch. Raw observations survive failed analytics checks. Credentials belong in the environment/GitHub secrets, never in files or logs.

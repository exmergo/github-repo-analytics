# Operate and extend the analytics

## Daily collection and publication

Enable `ANALYTICS_ENABLED=true` after setup. The workflow runs at 04:25 UTC or by manual dispatch. It serializes workflow runs and repository writes. Standard Ubuntu runners are used throughout; no paid model calls or hosted analytics service are required.

The workflow persists traffic and supplemental raw observations before validation. It then imports one immutable candidate across all configured projects, restores the accepted baseline, builds through Dex, checks the metrics and maintenance findings, and enforces freshness before publishing. `published.json` names the successful input/code commits and dependency-lock hash. A failure keeps the preceding publication pointer.

The very first successful build establishes a baseline. For a reviewed structural/metric change, manually dispatch with `accept_baseline=true`. The new baseline is generated only after the candidate builds and metric execution checks succeed. Normal scheduled runs never replace a baseline to hide drift.

For an optional real external-source smoke test, dispatch with `live_smoke=true`. Pull-request checks use synthetic inputs and do not receive collection secrets.

The data branch can contain upstream-generated reports; those are byproducts. This repo's agent answers use the tested MetricFlow definitions.

## Freshness and recovery

Run `uv run --frozen oss-analytics status --json`. Validation readiness, collection age, traffic lag, and missing dates are separate facts. Collection older than 48 hours (or twice the configured interval, whichever is larger) warns; older than seven days is critical. `status --require-fresh` also rejects traffic more than three calendar days behind. Exact historical answers can still be valid against old, clearly labeled data.

GitHub may delay/drop scheduled jobs and disables public-repository schedules after 60 days without activity. See [GitHub's schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule). Collection commits to the data branch every day, which normally counts as activity, but this template deliberately does not try to circumvent the rule. If **Actions** shows the workflow as disabled, re-enable it there; `status --json` reports the growing collection age either way. Verify that a workflow is enabled before assuming a quiet chart represents a quiet project.

Each project is collected in its own matrix job. One failing project does not block the others' raw data; validation still refuses to publish while any project is stale.

### Failures

A failed scheduled run opens, or comments on, a single **Analytics collection is failing** issue that links the run. Close it once a run succeeds. Signal collection is independent: a package-registry outage is recorded in `signals/capture.json` and `status` warnings, keeps the previous download history, and never blocks GitHub data.

A green run therefore does not prove every signal was collected. After the first run, and after rotating the token, read the warnings in the *Check model and metric contracts* step's `status` output. Each one names the signal and GitHub's own reason, for example `stargazers: api.github.com HTTP 403 ("Resource not accessible by personal access token")`, which means the token does not include that repository.

If collection stops:

1. Inspect the failed Actions run. Check the last successful snapshot and traffic dates.
2. Rotate an expired `GHRS_TOKEN` or correct permissions. Maintain an expiry reminder outside this workflow; a disabled scheduler cannot monitor itself.
3. Manually dispatch collection. Data still in GitHub's traffic window may be recovered by the upstream collector. Older missed traffic cannot be recreated; keep those gaps visible.
4. Build and check. Review structural/semantic changes before accepting a new baseline.

Publication provenance stores the immediate approved data/code revisions, lockfile identity and validation time. It does not embed earlier publications' source manifests. This keeps repeated imports of your own data branch bounded while retaining the current sources and their file checksums.

If an older installation reports `source file exceeds 32 MiB` while reading `published.json`, update to v1.1.0 or later and manually run collection/publication. CI imports its explicitly pinned raw candidate without reading the old publication pointer, then builds and checks before writing a compact replacement. For a single configured source, local `sync --revision <full-raw-commit-sha>` provides the same recovery entry point; follow it with build and check. Review any intended baseline change before accepting it. Ordinary imports continue using the approved pointer, and the download-size guard remains enforced.

Raw inputs survive a failed analytics check. A malformed new input cannot replace a previous sync candidate; an interrupted/failed build cannot replace the previous DuckDB file. The last published candidate remains available even if newer raw commits have failures. Remove unused local `.data/inputs/` generations only after confirming they are not referenced by `.data/sync.json` or `.data/build.json`.

### Adding a repository

A baseline taken while only one repository has data records keys such as `date` or issue `number` as unique. When a second repository arrives, the next check blocks publication with `key_lost_uniqueness` on those columns; the raw data is already saved. Confirm that each duplicate belongs to a different repository: build and check locally, or count distinct `(repository, date)` pairs with `dex explore query`. Then run the workflow manually with **accept_baseline** checked. [`.dex/review/README.md`](../.dex/review/README.md#follow-up-adding-a-second-repository-2026-10-22) walks through one real case.

## Dependencies

`pyproject.toml` declares dependencies and `uv.lock` records their resolved versions, package hashes, and platform/Python markers. The bootstrap runs `uv sync --locked`, which refuses a missing or stale lockfile. It uses Python 3.11 from `.python-version` unless you explicitly select another supported interpreter. CI installs from the same lock on Python 3.11 and 3.12.

Run tools with `uv run --frozen <command>` to use the recorded resolution without updating it. The environment still synchronizes to that lock; `--frozen` is not a substitute for CI's `uv sync --locked` freshness check. Publication records the SHA-256 of `uv.lock`, and changes to it invalidate prior analytics validation through the code digest.

To change declarations, edit `pyproject.toml` (or use `uv add`/`uv remove`), then run `uv lock`. For a deliberate package upgrade, run `uv lock --upgrade-package <name>`. Review and commit both files, synchronize with `uv sync --locked`, and run the complete suite. Confirm MetricFlow remains an Apache-2.0 release and compatible with Dex's semantic extra. Do not bypass a runtime incompatibility with handwritten metric SQL. Review each action upgrade and pin its exact commit.

## Release this template

Before enabling the Exmergo showcase (`exmergo/github-repo-analytics`):

- Run the full fixture suite and lint checks.
- Run the explicit public-example smoke test with network access.
- Create/push the public repository and mark it as a template in GitHub settings.
- Enable `ANALYTICS_ENABLED=true` and manually run collection/publication once.
- Confirm `published.json`, retained Dex artifacts, freshness, and a documented question against the published revision.

Repository settings, secrets, and a first hosted workflow run require access to the destination GitHub organization. No token values belong in command arguments, source files, or release notes.

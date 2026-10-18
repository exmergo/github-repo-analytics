# Set up your analytics repository

Create a public repository from the template, clone it, and run `bash scripts/bootstrap.sh`. The default `sources.yml` imports Dex's public example. Replace it with the projects you want to track.

## Import existing history

```yaml
repositories:
  - repository: your-org/project-a
    mode: import
    data_repository: your-org/project-a
    data_branch: github-repo-stats
    expected_refresh_hours: 24
```

The source branch must contain `your-org/project-a/ghrs-data/views_clones_aggregate.csv` and any available upstream star/fork and snapshot CSVs. A legacy upstream branch can be imported directly. A template-managed branch's `published.json` points to its last validated data commit, which is the default import target.

Run `sync`, `build`, `baseline`, and `check` as in the README. With a single configured project, `sync --revision <full-sha>` replays an exact input revision. For multiple projects, the sync manifest records each source's resolved commit independently.

## Collect projects you maintain

```yaml
repositories:
  - repository: your-org/project-a
    mode: collect
  - repository: your-org/project-b
    mode: collect
```

In **Settings → Secrets and variables → Actions**:

1. Add `GHRS_TOKEN`, a fine-grained token with **Administration: read** for traffic and **Contents: read/write** for the upstream action's data-branch writes. Select the tracked repositories and this analytics repository. The action uses one token; fine-grained permissions apply to the selected repositories. A fine-grained token has one resource owner, so this documented setup uses projects and an analytics repository under that owner.
2. Add repository variable `ANALYTICS_ENABLED` with value `true`.
3. Confirm Actions can write repository contents and push the dedicated `github-repo-stats` branch. Protect the default branch through your normal code review settings.
4. Manually run **Collect and validate repository analytics** once. It creates the data branch if necessary, retains raw observations, then publishes a validated revision. After publication, set `data_repository` to your analytics repository for local syncs; it defaults to the tracked repository if omitted.

For example, after the first workflow in `your-org/project-analytics`:

```yaml
repositories:
  - repository: your-org/project-a
    mode: collect
    data_repository: your-org/project-analytics
  - repository: your-org/project-b
    mode: collect
    data_repository: your-org/project-analytics
```

`data_repository` selects local import location; `mode: collect` controls what the scheduled workflow collects. All workflow writes go to the analytics repository running it. Private projects are excluded from this public template.

For scheduled imports only, no `GHRS_TOKEN` is needed: configure `mode: import`, keep its external `data_repository`, and enable `ANALYTICS_ENABLED`. The ordinary workflow token writes this analytics repo's data branch and reads public metadata.

To read this analytics repo's validated publication locally while keeping external import origins configured, run:

```bash
uv run --frozen oss-analytics sync --data-repository your-org/project-analytics
```

This overrides only the local import location. The scheduled `stage` step continues importing from each configured upstream origin.

**Collection publishes traffic statistics.** Verify that your maintainers want the aggregates, referrers, and popular paths visible publicly before enabling it. No visitor identifiers are collected.

## Add campaign context

Edit `seeds/annotations.csv`:

```csv
event_id,repository,event_date,kind,title,url
launch-post,your-org/project-a,2026-10-01,campaign,Launch post,https://example.com/launch
```

IDs must be unique in the file; dates are UTC; repositories must be configured. Release events are fetched automatically with stable IDs. Drafts are excluded. Prereleases are retained and only compared when you explicitly select their event ID.

Changing annotations changes the analytics definitions. Rebuild, review the change, accept the new baseline if appropriate, then check.

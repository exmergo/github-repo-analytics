# Set up your analytics repository

Create a repository from the template, clone it, and run `bash scripts/bootstrap.sh`. Make it private to track private repositories or to keep your numbers to yourself (see [Public or private](#public-or-private)). The default `sources.yml` has two public examples: it imports Dex's published history and collects this template's own traffic. Replace both with the projects you want to track. Keeping `exmergo/dex` would copy its history into your data branch every day, and keeping `exmergo/github-repo-analytics` fails collection, because your token cannot read another owner's traffic.

A repository created from the template opens a **Finish setting up repository analytics** issue with this checklist. Nothing is collected until you complete it.

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

### Why a personal token is needed

GitHub's traffic endpoints (views, clones, referrers, paths) require push access to each tracked repository, and the workflow's built-in `GITHUB_TOKEN` cannot read another repository's traffic. Star history needs it too: GitHub refuses to list another repository's stargazers with dates to the built-in token (HTTP 403), and a fine-grained token only gets them for repositories it includes. For public repositories, forks, issues, releases, and package downloads work without it, but the token also raises the API rate limit for large projects. For private repositories, everything needs it.

### Create the token

[Create a fine-grained token](https://github.com/settings/personal-access-tokens/new) with:

| Repositories | Permission | Why |
|---|---|---|
| Each tracked repository | **Administration: read** | Traffic API |
| This analytics repository | **Contents: read and write** | The collector commits to the `github-repo-stats` branch |
| Each private tracked repository | **Contents: read**, **Issues: read**, **Pull requests: read** | Releases, issues, and pull requests, which are public on public repositories |

Include every tracked repository in the token, including one you only import: a repository missing from the token's list loses star history (status reports `stargazers: api.github.com HTTP 403`), even when it is public.

Metadata: read is added automatically. A fine-grained token has one resource owner (you or one organization), so keep the tracked projects and the analytics repository under that owner. Organizations may require an owner to approve fine-grained tokens. If your organization blocks them, a classic token with the `repo` scope also works but grants far more access.

Set an expiry and a calendar reminder: an expired token fails collection, and the workflow then opens an **Analytics collection is failing** issue.

### Enable collection

1. **Settings → Secrets and variables → Actions → Secrets:** add `GHRS_TOKEN`.
2. **Settings → Secrets and variables → Actions → Variables:** add `ANALYTICS_ENABLED` = `true`.
3. If a branch ruleset covers all branches, exclude `github-repo-stats`. Protect `main` through your normal review settings.
   The default **Workflow permissions** setting can stay **Read**: each job that writes declares `contents: write` or `issues: write` itself. Organizations often block the read-and-write default (GitHub answers `409 Write permissions for workflows are disabled by the organization`), and the workflow does not need it.
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

`data_repository` selects local import location; `mode: collect` controls what the scheduled workflow collects. All workflow writes go to the analytics repository running it. A public analytics repository refuses private projects; see [Public or private](#public-or-private).

For scheduled imports only, no `GHRS_TOKEN` is needed: configure `mode: import`, keep its external `data_repository`, and enable `ANALYTICS_ENABLED`. The ordinary workflow token writes this analytics repo's data branch and reads public metadata. Star history is then unavailable, because GitHub lists stargazer dates only to a token that includes the repository; add `GHRS_TOKEN` covering it to collect them.

To read this analytics repo's validated publication locally while keeping external import origins configured, run:

```bash
uv run --frozen oss-analytics sync --data-repository your-org/project-analytics
```

This overrides only the local import location. The scheduled `stage` step continues importing from each configured upstream origin.

## Public or private

Collected data is as visible as the analytics repository that stores it. No visitor identifiers are collected either way.

| Analytics repository | Can track | Visible to |
|---|---|---|
| Public | Public repositories only; the workflow refuses a private one before reading any traffic | Anyone: verify that your maintainers want the aggregates, referrers, and popular paths published |
| Private | Public and private repositories | People with read access to the analytics repository |

A private analytics repository works the same way, with three differences:

- Its scheduled runs use the Actions minutes included in your plan instead of running free. One daily run is a few minutes.
- Local syncs need `GITHUB_TOKEN` (for example `export GITHUB_TOKEN=$(gh auth token)`), because private data branches are read through the API rather than public raw content.
- Making it public later publishes its whole history, including private projects' data. Remove them and their data branch first.

## What else is collected

Every `sync` (locally) and every scheduled run also collects public signals into `<owner>/<repo>/signals/`:

| File | Source | Stored |
|---|---|---|
| `stargazers.csv` | Stargazers API with `starred_at` | Stars per UTC day from current stargazers; no logins |
| `forks.csv` | Forks API | Existing forks per creation day; no owners |
| `issues.csv` | Issues API, incrementally | Number, kind, created/closed/merged times, author association; no titles, bodies, or logins |
| `downloads/<registry>/<package>.csv` | pypistats.org, api.npmjs.org | Daily downloads, merged by date because registries keep short windows |
| `capture.json` | | Capture time, completeness, and registry errors |

Repository metadata observations also record watchers, open issues and pull requests, and release asset download counts.

GitHub lists at most about 40,000 stargazers or forks. Larger projects are marked incomplete, and star history ends the day before the listing was cut off.

## Track package downloads (optional)

Add a `packages` block only for registries the project actually publishes to. Both lists are optional; a project without packages simply reports package downloads as unavailable.

```yaml
repositories:
  - repository: your-org/project-a
    mode: collect
    packages:
      pypi: [project-a]          # PyPI distribution name
      npm: ["@your-org/project-a"]
```

PyPI history comes from [pypistats.org](https://pypistats.org) without mirrors (about 180 days are available on first collection). npm comes from the [npm downloads API](https://github.com/npm/registry/blob/main/docs/download-counts.md) (up to a year back). Both include CI and bot traffic; they are downloads, not users or installations. Daily collection keeps history beyond each registry's window.

## Add campaign context

Edit `seeds/annotations.csv`:

```csv
event_id,repository,event_date,kind,title,url
launch-post,your-org/project-a,2026-10-01,campaign,Launch post,https://example.com/launch
```

IDs must be unique in the file; dates are UTC; repositories must be configured. Release events are fetched automatically with stable IDs. Drafts are excluded. Prereleases are retained and only compared when you explicitly select their event ID.

Changing annotations changes the analytics definitions. Rebuild, review the change, accept the new baseline if appropriate, then check.

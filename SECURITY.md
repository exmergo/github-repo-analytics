# Security policy

## Reporting a vulnerability

Report privately through [GitHub private vulnerability reporting](https://github.com/exmergo/github-repo-analytics/security/advisories/new). Do not open a public issue. We aim to acknowledge reports within three business days.

## What this template handles

- **Tokens.** Collection uses a fine-grained token stored as the `GHRS_TOKEN` Actions secret, and the workflow's own `GITHUB_TOKEN`. Tokens are read from the environment, sent only to `api.github.com`, and never written to files, logs, or the data branch. Package registries (`pypistats.org`, `api.npmjs.org`) never receive a token.
- **Published data.** Enabling collection publishes traffic aggregates, top referrers, popular paths, star and fork day counts, issue and pull request timestamps with GitHub's author association, and package download counts to the analytics repository's `github-repo-stats` branch, which anyone who can read that repository can see. No logins, names, emails, titles, or issue bodies are stored.
- **No private data in a public repository.** Before any traffic is read, collection refuses to collect or import a private repository into a public analytics repository. A private analytics repository may track public and private repositories. Making it public later publishes its whole history, including the data branch.
- **Network allowlist.** The HTTP client accepts only HTTPS requests to GitHub's API, raw content of public repositories, and the two package-statistics hosts, rejects cross-host redirects, and caps responses at 32 MiB.

## Supported versions

Only the latest commit on `main` is supported. Workflow actions are pinned by commit SHA and Python dependencies by `uv.lock`; Dependabot proposes updates weekly.

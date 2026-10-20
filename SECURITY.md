# Security policy

## Reporting a vulnerability

Report privately through [GitHub private vulnerability reporting](https://github.com/exmergo/github-repo-analytics/security/advisories/new). Do not open a public issue. We aim to acknowledge reports within three business days.

## What this template handles

- **Tokens.** Collection uses a fine-grained token stored as the `GHRS_TOKEN` Actions secret, and the workflow's own `GITHUB_TOKEN`. Tokens are read from the environment, sent only to `api.github.com`, and never written to files, logs, or the data branch. Package registries (`pypistats.org`, `api.npmjs.org`) never receive a token.
- **Published data.** Enabling collection publishes traffic aggregates, top referrers, popular paths, star and fork day counts, issue and pull request timestamps with GitHub's author association, and package download counts to the public `github-repo-stats` branch. No logins, names, emails, titles, or issue bodies are stored.
- **Public repositories only.** Collection refuses private repositories and a private analytics destination before any traffic is read.
- **Network allowlist.** The HTTP client accepts only HTTPS requests to GitHub's API, public raw content, and the two package-statistics hosts, rejects cross-host redirects, and caps responses at 32 MiB.

## Supported versions

Only the latest commit on `main` is supported. Workflow actions are pinned by commit SHA and Python dependencies by `uv.lock`; Dependabot proposes updates weekly.

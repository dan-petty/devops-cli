# Design

## Decisions

### Add a 3-day path-scoped entry to `.trivyignore.yaml`
`SECURITY.md:113` directs an agent to add a dated, path-scoped entry to `.trivyignore.yaml` when a pull request cannot fix the file.
The Harbor `template-task` Dockerfile lives inside `.venv/lib/python3.14/site-packages/harbor/`, which `uv sync` installs from the locked `harbor` package.
Set `expired_at: 2026-11-27`, three days from `2026-11-24`, matching the agent limit in `SECURITY.md:80`.

### Keep the exact virtualenv path
Match the path `.venv/lib/python3.14/site-packages/harbor/cli/template-task/environment/Dockerfile` used by the existing `DS-0029` and `DS-0002` entries in `.trivyignore.yaml:22-31`.
This scopes the suppression strictly to alert 1189 without wildcard matching (`SECURITY.md:90`).

## Rejected alternatives

- **Edit the Dockerfile under `.venv`**: `uv sync` overwrites local edits inside `.venv/lib/python3.14/site-packages/harbor/cli/template-task/environment/Dockerfile`.
- **Set `expired_at` to 90 days**: `SECURITY.md:80` and `SECURITY.md:113` limit an agent to a 3-day entry (renewed up to 14 days total). A 90-day expiry requires an owner decision.
- **Dismiss alert 1189 in GitHub code scanning**: `SECURITY.md:114` states that an agent does not dismiss an alert, and a GitHub dismissal leaves no expiring record in `.trivyignore.yaml`.
- **Use a wildcard path glob**: `SECURITY.md:90` forbids wildcards in ignore entries.

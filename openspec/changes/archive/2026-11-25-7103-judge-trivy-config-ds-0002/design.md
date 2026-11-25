# Design

## Decisions

- Add one `misconfigurations` entry for `id: DS-0002` scoped to `.venv/lib/python3.14/site-packages/harbor/cli/template-task/pytest-tests/Dockerfile`, with `expired_at: 2026-11-28` (3 days from `2026-11-25` per `SECURITY.md` "Judging a Trivy-config Alert" and "A Finding with No Fix").
- Keep the exact path under `.venv/` rather than using wildcards (`SECURITY.md` forbids wildcards in ignore entries).

## Rejected alternatives

- **Edit the Dockerfile inside `.venv/`**: `uv sync` overwrites installed package files and no commit tracks `.venv/`.
- **Dismiss alert 1192 in GitHub code scanning**: `SECURITY.md` states an agent does not dismiss alerts in code scanning.
- **Add a wildcard rule under `.venv/` or set a longer expiry**: `SECURITY.md` forbids wildcards and caps agent ignore entries at 3 days initially.

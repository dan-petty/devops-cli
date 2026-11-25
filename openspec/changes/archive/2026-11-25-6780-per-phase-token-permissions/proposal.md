# Proposal: #6780

## Why
Each GitHub App installation token of a roadmap Job asks for one shared set `CONST_GITHUB_APP_TOKEN_PERMISSIONS` in `src/devops_cli/config/constants.py`, which includes `contents: write`, `pull_requests: write`, `issues: write`, and `workflows: write`. Since #3700 shipped, `prepare` and `publish` run in separate containers and mint their own tokens. `prepare` only reads the repository and pull requests while writing issue status and marks, yet its token still grants `contents: write` and `workflows: write`. `publish` grants `workflows: write` on every item even when the merged plan modifies no file under `.github/workflows/`.

## What Changes
- Add per-phase token permission maps in `src/devops_cli/config/constants.py`: `CONST_GITHUB_APP_PREPARE_TOKEN_PERMISSIONS` (`contents: read`, `pull_requests: read`, `issues: write`, `checks: read`, `actions: read`, with no `workflows` key) and `publish_token_permissions(*, workflows: bool = False)` (based on `CONST_GITHUB_APP_PUBLISH_TOKEN_PERMISSIONS` with `contents: write`, `pull_requests: write`, `issues: write`, `checks: read`, `actions: read`, `metadata: read`, adding `workflows: write` only when `workflows=True`).
- Accept an explicit permission map parameter on `configured_app` and `mint_installation_token` in `src/devops_cli/github/app_installation.py` and track active phase token permissions via `token_permissions_scope` in `src/devops_cli/core/process.py`, refreshing cached tokens whenever the active permission set changes.
- Scope every `prepare` and `publish` entrypoint (`implement`, `stage`, `fix-checks`, `fix-conflict`) so `prepare` uses the prepare permissions, `stage` `publish` uses `workflows=False`, and `implement`/`fix-checks`/`fix-conflict` `publish` enables `workflows: write` only when the merged plan on GitHub names a workflow path.
- Update ADR 0030 (`docs/adr/0030-roadmap-steps-run-their-agent-apart-from-the-app-key.md`), `docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md` (`## Status History`), `docs/CLUSTER.md`, and `SECURITY.md` to match the per-phase permissions.

## Capabilities
- `github-app-identity`: Scoped GitHub App installation token permissions for the `prepare` and `publish` phases, with `workflows: write` gated on workflow paths in the merged plan.

## Impact
- `prepare` containers and calls no longer ask for `contents: write` or `workflows: write`.
- `publish` requests `workflows: write` only when `merged_workflows` finds a `.github/workflows/` path in the merged plan on GitHub.
- `devops-cli-service` and unscoped CLI calls keep `CONST_GITHUB_APP_TOKEN_PERMISSIONS` (and metrics/read-only rules).

## Feasibility
Verified against `origin/main`:
- Dependency #6691 is closed (`State: closed`).
- All four phased workflows (`implement_phases.py`, `stage_job_phases.py`, `fix_checks_phases.py`, `fix_conflict_phases.py`) run `prepare` and `publish` separately or in sequence via `core/process.py:_lookup_session_token` -> `app_installation.mint_installation_token`.
- `docs/adr/0030-roadmap-steps-run-their-agent-apart-from-the-app-key.md` has `status: proposed`, so line 44 (`Until #3700, one process mints one token...`) can be edited directly without violating ADR body immutability, while accepted `docs/adr/0015-...` updates via `## Status History`.

## Existing Tool Considered
The alternatives check on #6780 recorded verdict `none` (`Tool: none found`): no external tool mints this repository's per-phase `prepare` and `publish` permission maps from `constants.py` or updates the phase callers, tests, and ADRs in-house. Cost to build in-house is roughly 2,500 tokens of edits and local verification.

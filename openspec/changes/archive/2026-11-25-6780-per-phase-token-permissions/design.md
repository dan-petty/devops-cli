# Design

## Decisions
1. **Per-phase constants beside `CONST_GITHUB_APP_TOKEN_PERMISSIONS` (`src/devops_cli/config/constants.py`):**
   - `CONST_GITHUB_APP_PREPARE_TOKEN_PERMISSIONS` defines `{actions: read, checks: read, contents: read, issues: write, pull_requests: read}`.
   - `CONST_GITHUB_APP_PUBLISH_TOKEN_PERMISSIONS` defines `{actions: read, checks: read, contents: write, issues: write, metadata: read, pull_requests: write}` and `publish_token_permissions(*, workflows: bool = False)` returns a fresh dict with `workflows: write` added only when `workflows=True`.
   - When `service.github_app.read_only` is true, `configured_app` still forces `CONST_GITHUB_APP_READ_TOKEN_PERMISSIONS` so a read-only process cannot widen its token.
2. **Thread/context-scoped permission binding and automatic token invalidation (`src/devops_cli/core/process.py`, `src/devops_cli/github/app_installation.py`):**
   - `configured_app(permissions=...)` and `mint_installation_token(app=None, *, permissions=...)` accept an explicit permission map parameter.
   - `token_permissions_scope(permissions)` in `src/devops_cli/core/process.py` stores the active map in a `ContextVar`, and `_session_github_token()` tracks the permission set associated with `_github_token` so any transition between unscoped, `prepare`, `publish` (`workflows=False`), and `publish` (`workflows=True`) re-mints when the requested permissions change (including `--phase all`).
3. **Phase entrypoints (`commands/roadmap.py`, `implement_phases.py`, `stage_job_phases.py`, `fix_checks_phases.py`, `fix_conflict_phases.py`):**
   - All `prepare` entrypoints (and `_implement_phase` planning before `prepare_implement`) run inside `token_permissions_scope(CONST_GITHUB_APP_PREPARE_TOKEN_PERMISSIONS)`.
   - `stage` `publish` runs inside `token_permissions_scope(publish_token_permissions(workflows=False))`, since stage never pushes workflow files.
   - `implement`, `fix-checks`, and `fix-conflict` `publish` start inside `token_permissions_scope(publish_token_permissions(workflows=False))` (to read the item, check runs, logs, and `merged_workflows` from GitHub), and enter `token_permissions_scope(publish_token_permissions(workflows=True))` for the push only when the resolved `workflow_paths` tuple is non-empty.
4. **Documentation updates:**
   - Remove the `Until #3700` token sentence in `docs/adr/0030-roadmap-steps-run-their-agent-apart-from-the-app-key.md` (`status: proposed`).
   - Add a concise `## Status History` entry in accepted `docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md` without modifying its frozen body, and align `docs/CLUSTER.md` and `SECURITY.md`.

## Rejected alternatives
- **Single read-only set for `prepare`:** Rejected because `prepare` calls `write_status`, `set_marks`, `StageWriter.begin`, `settle`, and `judge_round`, which require `issues: write`.
- **Keep `CONST_GITHUB_APP_TOKEN_PERMISSIONS` unchanged for both phases:** Rejected because `prepare` does not need `contents: write` or `workflows: write`, and `publish` rarely changes `.github/workflows/`.
- **Always request `workflows: write` in `publish`:** Rejected because only plans naming `.github/workflows/` paths need it.
- **Store `workflows` flag in local `state/`:** Rejected because `publish` reads `merged_workflows` directly from GitHub (`ADR 0030`) rather than trusting run-folder state alone for security decisions.

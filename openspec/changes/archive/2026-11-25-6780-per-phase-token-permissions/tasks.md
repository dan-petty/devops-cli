# Tasks

## 1. Per-phase token permissions (behavior)

- [x] 1.1 Add failing tests in `tests/github/test_github_app_identity.py` and `tests/roadmap/implement/test_roadmap_implement_phases.py` covering `prepare` permissions, `publish` permissions with and without `.github/workflows/`, and ADR 0030 having no `Until #3700` token line.
  - Verification: `$ uv run pytest -n 0 tests/github/test_github_app_identity.py tests/roadmap/implement/test_roadmap_implement_phases.py -k "prepare or workflows or adr_0030"`
- [x] 1.2 Define `CONST_GITHUB_APP_PREPARE_TOKEN_PERMISSIONS`, `CONST_GITHUB_APP_PUBLISH_TOKEN_PERMISSIONS`, and `publish_token_permissions` in `src/devops_cli/config/constants.py`, add `permissions` parameter support in `src/devops_cli/github/app_installation.py` and `token_permissions_scope` in `src/devops_cli/core/process.py`, and wire `prepare` / `publish` scopes across `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/implement/implement_phases.py`, `src/devops_cli/roadmap/stage/stage_job_phases.py`, `src/devops_cli/roadmap/steps/fix_checks_phases.py`, and `src/devops_cli/roadmap/steps/fix_conflict_phases.py`.
  - Verification: `$ uv run pytest -n 0 tests/github/test_github_app_identity.py tests/roadmap/implement/test_roadmap_implement_phases.py tests/roadmap/stage/test_roadmap_stage_publish.py tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py tests/roadmap/steps/test_roadmap_step_fix_conflict.py`

## 2. Documents (other)

- [x] 2.1 Remove the `Until #3700` token sentence in `docs/adr/0030-roadmap-steps-run-their-agent-apart-from-the-app-key.md`, add a `## Status History` note in `docs/adr/0015-roadmap-jobs-act-as-a-github-app-on-the-personal-account.md`, and update `docs/CLUSTER.md` and `SECURITY.md` with per-phase permissions.
  - Verification: `$ rg -n 'Until #3700.*token|token keeps.*workflows: write' docs/adr/0030-roadmap-steps-run-their-agent-apart-from-the-app-key.md`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

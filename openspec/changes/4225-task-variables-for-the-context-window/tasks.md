# Tasks

## 1. Task variables for the window and the reply limit

Reads: `src/devops_cli/config/settings.py`, `src/devops_cli/config/env.py`. Changes: `src/devops_cli/config/settings.py`, `tests/config/test_ai_task_settings_paths.py`, `tests/security/test_config_declarations.py`.

- [x] 1.1 Write the tests that set each variable and read `for_task(task)`, and add the six names to the expected set of variables, and watch them fail on origin/main
  - Verification: `$ uv run devops ci test tests/config/test_ai_task_settings_paths.py` fails on the base
- [ ] 1.2 Add `_TASK_WINDOW_VARIABLES` to `src/devops_cli/config/settings.py`, give `analysis` and `stage` the fields of both tuples, and give `verification` a `Variable` marker with the second tuple
  - Verification: `$ uv run devops ci test tests/config/test_ai_task_settings_paths.py` passes
  - Verification: `$ uv run devops ci test tests/security/test_config_declarations.py` passes

## 2. Documents

Reads: `docs/ENV_VARS.md`, `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ENV_VARS.md`, `docs/ROADMAP_WORKFLOW.md`.

- [ ] 2.1 Run `uv run devops docs generate` so `docs/ENV_VARS.md` lists the six variables, and tell the window and reply-limit variables of the stage task in `docs/ROADMAP_WORKFLOW.md`
  - Verification: `$ git grep -n "AI_TASK_STAGE_CONTEXT_WINDOW" -- docs/ENV_VARS.md docs/ROADMAP_WORKFLOW.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

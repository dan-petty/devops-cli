# Tasks

## 1. The default ceiling follows the loaded step budget

Kind: behavior. Reads: `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/roadmap/implement/implement_limits.py`. Changes: `tests/roadmap/implement/test_roadmap_implement_extension.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`.

- [x] 1.1 Add the tests of a budget of 17000000 with no ceiling (config file and variable), and of a budget of 12000000 with no ceiling that gets its whole extension. Run them and see them fail
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_extension.py` fails on the base
- [x] 1.2 Give `step_token_ceiling` a default factory of twice the loaded budget, replace `DEFAULT_ROADMAP_IMPLEMENT_STEP_TOKEN_CEILING` with `CONST_ROADMAP_IMPLEMENT_CEILING_FACTOR`, and update the table of the roadmap limits
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_extension.py tests/roadmap/test_roadmap_limit_classes.py tests/config` passes

## 2. Documents

Kind: other. Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `src/devops_cli/config/settings.py`, `docs/ROADMAP_WORKFLOW.md`, `docs/ENV_VARS.md`.

- [x] 2.1 State the default of the ceiling in its description and in `docs/ROADMAP_WORKFLOW.md`, and regenerate the documents
  - Verification: `$ uv run devops docs generate --sync-readme` leaves no further diff

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

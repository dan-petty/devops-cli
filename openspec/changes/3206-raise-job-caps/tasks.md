# Tasks

## 1. Make the time limits settings and the output cap a share of the window

Kind: behavior. Reads: `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_pull.py`, `tests/roadmap/test_roadmap_implement_step_output_cap.py`. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/implement_hooks.py`, `src/devops_cli/roadmap/implement_scoped_ci.py`, `src/devops_cli/roadmap/implement_pull.py`, `tests/roadmap/test_roadmap_implement_timeouts.py` (new), `tests/roadmap/test_roadmap_implement_step_output_cap.py`, `tests/roadmap/test_roadmap_implement_hooks.py`, `tests/invariants/test_k8s_manifests.py`, `tests/security/test_config_declarations.py`.

- [x] 1.1 Write failing tests in `tests/roadmap/test_roadmap_implement_timeouts.py` for the scenarios of "The time limits of the implement job are settings": the defaults, the variables, the config file, a limit of zero, the deadline of a model call, the limit of a scoped command and the seconds of the watch
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_timeouts.py` fails on the base
- [x] 1.2 Add the three settings and their defaults, delete the three constants, make each reader ask the settings, and make the output cap `output_cap(window)`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_timeouts.py tests/roadmap/test_roadmap_implement_step_output_cap.py tests/roadmap/test_roadmap_implement_hooks.py tests/security/test_config_declarations.py`
- [x] 1.3 Change the tests that held the old constants to the defaults, the settings and `output_cap`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step.py tests/roadmap/test_roadmap_implement_command.py tests/invariants/test_k8s_manifests.py`

## 2. Pass the window to every investigation and drop the stage output tokens

Kind: behavior. Reads: `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/roadmap/stage_toolbox.py`, `tests/roadmap/test_roadmap_refine_investigation.py`, `tests/roadmap/test_roadmap_stage_toolbox.py`. Changes: `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/roadmap/refine.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_toolbox.py`, `tests/roadmap/test_roadmap_refine_investigation.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_stage_toolbox.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_eval_run.py`.

- [x] 2.1 Write failing tests for the scenarios of "The investigation reads the context window of the analysis task", "The check reads the context window of the analysis task" and "A plan run has a budget" (the output tokens have no limit)
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine_investigation.py tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_stage_toolbox.py` fails on the base
- [x] 2.2 Move `analysis_window` to `refine_investigation.py`, pass it from refine and the alternatives check, and drop `output_tokens_limit` from the stage run
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_refine_investigation.py tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_stage_toolbox.py tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_stage_eval_run.py`

## 3. Raise the caps and add the class table

Kind: behavior. Reads: `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `k8s/devops/configmap.example.yaml`. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`, `tests/roadmap/test_roadmap_limit_classes.py` (new), `tests/roadmap/test_roadmap_stage_settings.py`, `tests/roadmap/test_roadmap_stage_apply.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_implement_step.py`.

- [x] 3.1 Write `tests/roadmap/test_roadmap_limit_classes.py` with the table of every limit, the list of removed names and the window checks
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_limit_classes.py` fails on the base
- [x] 3.2 Raise the caps as the design lists, and set the step budget to half of the implement window
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_limit_classes.py tests/roadmap/test_roadmap_stage_settings.py tests/roadmap/test_roadmap_stage_apply.py tests/roadmap/test_roadmap_stage_plan.py`
- [x] 3.3 Change the tests that held the old numbers to the constants
  - Verification: `uv run devops ci test tests/roadmap`

## 4. Documents

Kind: other. Reads: `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`. Changes: `docs/ENV_VARS.md`, `docs/CONFIGURATION.md`.

- [x] 4.1 Generate the documents again
  - Verification: `uv run devops docs check`

## 5. Archive

Kind: other.

- [x] 5.1 Archive the change
  - Verification: `uv run devops openspec archive 3206-raise-job-caps` and `uv run devops openspec check`

## Workflow follow-up

- Pending a person: remove `step_tokens: 40000` from `k8s/devops/configmap.example.yaml`, or set 64000, so the Service uses the new budget (the example sits under the Job deadline change).
- Pending a person: the stall of the progress-based Job deadline must stay above the new watch limit of 3600 s plus its margin.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

# Tasks

## 1. The limits are settings with a ceiling

Kind: behavior. Reads: `src/devops_cli/config/constants.py`, `src/devops_cli/config/settings.py`. Changes: `src/devops_cli/config/settings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py`, `tests/roadmap/test_roadmap_limit_classes.py`. Creates: `tests/config/test_roadmap_job_limit_settings.py`.

- [x] 1.1 Write `test_each_new_setting_has_the_old_constant_as_its_default`, `test_the_gate_returns_and_the_head_attempts_can_double`, `test_every_setting_loads_at_its_ceiling`, `test_a_value_above_the_ceiling_is_refused_with_the_name_of_the_setting`, `test_an_inner_limit_above_its_outer_limit_is_refused_with_both_names` and `test_the_live_doubled_values_load` in `tests/config/test_roadmap_job_limit_settings.py`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 1.2 Add the settings of `roadmap.stage`, `roadmap.implement` and `roadmap.fix_plan` with their defaults, `CONST_ROADMAP_LIMIT_CEILING_FACTOR` and the order checks; remove the constants and update the limit table
  - Verification: `$ uv run devops ci test tests/config/test_roadmap_job_limit_settings.py tests/roadmap/test_roadmap_limit_classes.py`

## 2. The jobs read the settings at each use

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/implement/implement_step.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/roadmap/stage/stage_tools.py`, `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/stage/stage_findings.py`, `src/devops_cli/roadmap/stage/stage_eval_render.py`, `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/implement/implement_tool_log.py`, `src/devops_cli/roadmap/implement/implement_limits.py`, `src/devops_cli/roadmap/implement/implement_eval_run.py`, `src/devops_cli/ai/tasks/roadmap_stage_tools.md`, `src/devops_cli/ai/tasks/roadmap_stage_verify_tools.md`, `src/devops_cli/telemetry/instruments.py` and the tests of these modules. Creates: `tests/roadmap/steps/test_roadmap_fix_plan_bounds.py`.

- [x] 2.1 Write `test_doubled_settings_select_a_plan_at_the_old_bounds`, `test_the_setting_gives_an_item_more_extra_returns`, `test_the_setting_raises_the_ceiling_of_the_repair_rounds`, `test_the_setting_moves_the_limit_of_refused_plans`, `test_the_prompts_name_the_budgets_of_the_settings`, `test_a_toolbox_run_reads_its_call_limit_from_the_settings`, `test_the_settings_set_the_limits_of_the_refusals_and_of_the_failures_of_a_tool`, `test_the_settings_set_the_window_and_the_refused_commands_of_the_rule` and `test_the_settings_set_the_resends_and_the_request_limit_of_a_step`
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [x] 2.2 Read each setting where the constant was read; give `gate_extension`, `repair_round_due`, `progress_digest` and `extends` the limit as an argument; give the prompts the placeholders of the call budget; give the file tools of the harness `tool_retries`
  - Verification: `$ uv run devops ci test src/devops_cli/roadmap/stage/stage.py src/devops_cli/roadmap/steps/fix_plan.py src/devops_cli/roadmap/implement/implement_step.py src/devops_cli/roadmap/implement/implement_tool_log.py src/devops_cli/roadmap/implement/implement_limits.py`

## 3. Document the settings

Kind: other. Reads: `docs/roadmap/stage.md`. Changes: `docs/CLUSTER.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `docs/roadmap/implement.md`, `docs/adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md`, `docs/CONFIGURATION.md`, `docs/ENV_VARS.md`, `docs/TELEMETRY.md`.

- [x] 3.1 Name the settings in place of the constants in the documents, add the Status History line of ADR 0021, and regenerate the documents of the settings and the metrics
  - Verification: `$ uv run devops docs generate`

## Criteria

- Group 1: `uv run pytest tests/config/test_roadmap_job_limit_settings.py` passes: each new setting has the old constant as its default, `roadmap.stage.gate_returns: 6` and `roadmap.fix_plan.head_attempts: 4` load, and a value above the ceiling fails with the name of the setting.
- Group 2: `uv run pytest tests/roadmap/steps/test_roadmap_fix_plan_bounds.py` passes: with `head_attempts: 4` and `revisions: 6`, the step selects a plan with 2 attempts on its head or 3 revisions.
- Group 3: `uv run devops docs check` passes with the new settings in `docs/CONFIGURATION.md` and `docs/ENV_VARS.md`.
- Pending a person, after the release: the ConfigMap `devops-cli-config` sets the doubled values of the new settings, and the next stage, implement and fix-plan result lines show runs past the old limits, such as `gate_returns=4` or more.

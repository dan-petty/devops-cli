# Proposal: #5440

## Why

On 2026-11-13 the owner asked to double every limit of the roadmap jobs that are below 80 % success (stage 1 of 4, implement 1 of 3 in 6 hours, and fix-plan runs that end in `timeout`), and to try configuration values until one works. The live ConfigMap holds the doubled values of each setting of these jobs. But many limits that end an attempt are constants, so a person cannot change them without a release, and the ceiling of `roadmap.stage.gate_returns` (3) stops a doubled value.

Closes #5440.

## What Changes

- Each limit below becomes a setting of its job section, with the value of the constant as its default. A job reads it when the round, the step or the selection starts, so a changed ConfigMap needs no restart.
  - `roadmap.stage`: `gate_return_extensions` (1), `verify_repair_rounds_ceiling` (4), `plan_defect_limit` (3), `max_requests` (250), `max_tool_calls` (200), `plan_calls_advised` (30), `plan_calls_notice` (40), `review_calls_advised` (40) and `review_calls_notice` (60).
  - `roadmap.implement`: `max_requests` (500), `max_tool_calls` (1500), `tool_retries` (5), `max_refusals` (30), `max_consecutive_refusals` (3), `model_resends` (1), `extension_calls` (20) and `extension_max_refused` (3).
  - `roadmap.fix_plan`: `head_attempts` (2) and `revisions` (3).
- The settings load refuses a value above 4 times the default (`CONST_ROADMAP_LIMIT_CEILING_FACTOR`), with the name of the setting in the error. So `gate_returns` can go to 12 and `verify_repair_rounds` to 16. The Job deadline keeps its cap of 14400 s (`CONST_ROADMAP_IMPLEMENT_DEADLINE_CAP_SECONDS`), because the admission policy `roadmap-service-jobs` refuses more. This change does not touch that policy.
- The settings load refuses an inner limit above its outer limit, with the names of both settings: `verify_repair_rounds` above `verify_repair_rounds_ceiling`, an advice above its notice, a notice above `max_tool_calls`, `max_consecutive_refusals` above `max_refusals`, and `extension_max_refused` above `extension_calls`. The time order check of the implement deadline (`deadline_stall_seconds`, `deadline_extension_seconds`, `item_time_limit_seconds` and `deadline_ceiling_seconds`) does not change.
- The prompts of a plan run and of a review run get the call budget from the settings through `{{plan_calls_advised}}`, `{{plan_calls_notice}}`, `{{review_calls_advised}}` and `{{review_calls_notice}}`.
- The file tools of the harness take `roadmap.implement.tool_retries` in place of the 5 of `Coder`, so the setting changes the retries of every tool.
- The constants `CONST_ROADMAP_STAGE_GATE_RETURNS_CEILING` and `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING` and the 18 listed limit constants go. The limit table test holds that none comes back.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/run-limits`, `roadmap-stage/returns`, `roadmap-stage/verification`, `roadmap-stage/toolbox` and `roadmap-stage/fix-plan`: the limits are settings with a ceiling of 4 times the default.
- `roadmap-implement-step/budgets`, `roadmap-implement-step/shell`, `roadmap-implement-step/model-calls` and `roadmap-implement-step/trace`: the limits of a step are settings.

## Impact

- Code: `src/devops_cli/config/settings.py`, `defaults.py` and `constants.py`; `src/devops_cli/roadmap/stage/stage.py`, `stage_toolbox.py`, `stage_tools.py`, `stage_verify.py`, `stage_findings.py` and `stage_eval_render.py`; `src/devops_cli/roadmap/implement/implement_step.py`, `implement_tool_log.py`, `implement_limits.py`, `implement_eval_run.py` and `implement_shell_refusal.py`; `src/devops_cli/roadmap/steps/fix_plan.py`; the prompts `roadmap_stage_tools.md` and `roadmap_stage_verify_tools.md`; the description of `devops_cli_roadmap_stage_gate_problems`.
- Documents: `docs/CLUSTER.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/stage.md`, `docs/roadmap/implement.md`, one Status History line of ADR 0021, and the generated `docs/CONFIGURATION.md`, `docs/ENV_VARS.md` and `docs/TELEMETRY.md`.
- With no configuration, no job changes. The plan cache key holds the prompts with their placeholders, so the change of the prompt text makes the cached plans new once.
- The Service and the runner image read the settings, so the change needs a release. After the release, a person or an agent sets the doubled values of the new settings in the ConfigMap `devops-cli-config`.

## Feasibility

- Source at `origin/main` 87e813d5b: `grep -rn` finds each listed constant in `src/devops_cli/config/constants.py` and its readers: `stage_toolbox.py:77-79` (`_RUN_LIMITS`), `stage_findings.py:352` (`gate_extension`), `stage_verify.py:464` (`repair_round_due`), `stage.py:1792` and `stage.py:3416` (the repair rounds and the plan defect limit), `fix_plan.py:380` and `fix_plan.py:393` (the bounds of the selection), `implement_step.py:186-187`, `:679` and `:867` (the usage limits, the tool retries and the resends), `implement_tool_log.py:133`, `:351`, `:503` and `:509` (the window and the refusals) and `implement_limits.py:136` (the rule of the extension). `settings.py:1067` holds `le=CONST_ROADMAP_STAGE_GATE_RETURNS_CEILING`, so `gate_returns: 6` fails the settings load today.
- The live ConfigMap `devops-cli-config`, read with `kubectl -n devops get configmap devops-cli-config` on 2026-11-13, holds the doubled values of each existing setting (`verify_repair_rounds: 4`, `repair_rounds: 6`, token budgets of 16 M and 40 M, step 10800 s, item 14400 s, `deadline_extension_seconds: 10800`, `max_memory_limit: 16Gi`, `fix_plan.time_budget_seconds: 7200`), and no `gate_returns`, because its ceiling is 3. The new order checks pass on these values.
- `k8s/devops/roadmap-service/admissionpolicy.yaml` refuses `activeDeadlineSeconds` above 14400, so the cap of the Job deadline stays.
- `pydantic_ai_harness/coder/_capability.py` gives the file tools `max_retries=MAX_FILE_TOOL_RETRIES` (5). The retries of the agent (`retries={"tools": ...}`) do not reach them, so the step also replaces `max_retries` of the `FileSystem` capability. A test that sets `tool_retries: 2` proves it.

## Existing Tool Considered

The pydantic settings of the project (`Field` with `ge` and `le`, and a `model_validator` for the order of two settings) hold the job settings, and the ConfigMap is the existing control. No new tool. Cost to build: about 0.6 M tokens and 3 hours. Keep: one field for each limit. Fix: about 0.1 M tokens for each wrong default.

## Dependencies

#5413 changes `src/devops_cli/roadmap/steps/fix_plan.py` in parallel (attempt classes, `fix_plan.version`, `--skip-wait`). This change touches only the two lines that read the bounds and the module docstring there, so the pull request that merges second rebases with a small conflict at most.

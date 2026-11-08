# Tasks

## 1. Time the checks, the publish and the watch of the implement job

Reads: `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/step_metrics.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/telemetry/instruments.py`. Changes: `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/step_metrics.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/telemetry/instruments.py`, `tests/telemetry/test_roadmap_intake_implement_metrics.py`, `tests/roadmap/test_roadmap_failure.py`, `tests/telemetry/test_roadmap_stage_steps.py`.

- [ ] 1.1 Add the `implement_step` and `step_names` cases to `tests/telemetry/test_roadmap_intake_implement_metrics.py`, and extend the `StepName` tests of `tests/roadmap/test_roadmap_failure.py` and `tests/telemetry/test_roadmap_stage_steps.py`. Run them and see them fail on the base
  - Verification: `$ uv run devops ci test tests/telemetry/test_roadmap_intake_implement_metrics.py -k "implement_step or step_names"` fails on the base
- [ ] 1.2 Add `CHECKS`, `PUBLISH` and `WATCH` to `StepName`. Make `observe_step` yield a handle with `fail()` that sets the result `error`, and add the helpers that time one call for the implement row. Extend the text of `ROADMAP_STEP_SECONDS` with the 6 series of the implement row
  - Verification: `$ uv run devops ci test tests/telemetry/test_roadmap_stage_steps.py tests/roadmap/test_roadmap_failure.py tests/telemetry/test_telemetry_instruments.py` passes
- [ ] 1.3 In `implement_run.py`, time `_scoped_checks`, the publish branch of `_push` and both `watch_pull` calls of `_checks`, and touch neither `_groups` nor `_start`
  - Verification: `$ uv run devops ci test tests/telemetry/test_roadmap_intake_implement_metrics.py -k "implement_step or step_names" tests/roadmap/implement` passes
  - Verification: `$ git diff origin/main -- src/devops_cli/roadmap/implement/implement_run.py | grep -c '^[-+].*\b_groups\b\|^[-+].*def _start'` prints 0

## 2. Count the outcome of each intake candidate

Reads: `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/roadmap/tool_metrics.py`. Changes: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/intake/intake.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/commands/roadmap.py`, `tests/support/roadmap_intake.py`, `tests/roadmap/intake/test_roadmap_intake_agent_candidates.py`, `tests/roadmap/intake/test_roadmap_intake_dry_run.py`, `tests/roadmap/intake/test_roadmap_intake_duplicates.py`, `tests/roadmap/intake/test_roadmap_intake_item_changed.py`, `tests/roadmap/intake/test_roadmap_intake_model_reply.py`, `tests/roadmap/intake/test_roadmap_intake_untrusted_text.py`.

- [ ] 2.1 Add the `intake_outcome` cases to `tests/telemetry/test_roadmap_intake_implement_metrics.py`. Run them and see them fail on the base
  - Verification: `$ uv run devops ci test tests/telemetry/test_roadmap_intake_implement_metrics.py -k intake_outcome` fails on the base
- [ ] 2.2 Declare `ROADMAP_INTAKE_CANDIDATES_TOTAL` (counter, unit `1`, "4 series") in `instruments.py`, and add it to `INSTRUMENTS` and `__all__`
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry_instruments.py` passes
- [ ] 2.3 Give `apply_intake` the required keyword `repo`, count each candidate once under its result, send the four zeros in `_apply_round`, and pass the repository at each caller (`intake_candidate`, `_apply_round`, `commands/roadmap.py`, `_file_deferrals`). Pass `repo` at each call of `apply_intake` in the tests
  - Verification: `$ uv run devops ci test tests/telemetry/test_roadmap_intake_implement_metrics.py tests/roadmap/intake tests/roadmap/test_roadmap_run_metrics.py` passes
  - Verification: `$ ! git grep -nE 'apply_intake\((store|roadmap\.store), (plan|deferral\.plan)\)' src/ tests/` exits 0

## 3. Document the series

Reads: `docs/TELEMETRY.md`, `src/devops_cli/docs/generator.py`. Changes: `docs/TELEMETRY.md`.

- [ ] 3.1 Run `uv run devops docs generate --sync-readme` so that `docs/TELEMETRY.md` lists the counter, the series counts and the untimed push of a stop
  - Verification: `$ grep -q devops_cli_roadmap_intake_candidates_total docs/TELEMETRY.md` exits 0
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 1: The implement job sends one `checks`, one `publish` and one `watch` sample with `row` `implement`.
- Group 1: A failed check of the pull request has the result `error`, and the `publish` sample excludes the scoped checks.
- Group 1: The step values are members of `StepName`.
- Group 2: `apply_intake` adds 1 for each candidate under `placed`, `duplicate`, `skipped` or `failed`.
- Group 2: The intake round sends 0 for each of the four results before its first candidate.
- Group 3: `docs/TELEMETRY.md` lists `devops_cli_roadmap_intake_candidates_total` and the series counts.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

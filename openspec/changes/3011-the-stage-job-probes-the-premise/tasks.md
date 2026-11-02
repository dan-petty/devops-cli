# Tasks

## 1. Expose the cited items of the issue

Reads: `src/devops_cli/roadmap/refine.py`, `tests/roadmap/test_roadmap_refine.py`. Changes: `src/devops_cli/roadmap/refine.py`.

- [x] 1.1 In `src/devops_cli/roadmap/refine.py`, add the public `cited_paths(body)` and `cited_identifiers(body)` on the two patterns of `collect_context`, rename the private `_git` to the public `git_result`, and make `_collect_cited_files`, `_collect_identifiers` and `_collect_symbol_sections` call them. The behavior of `collect_context` stays the same. Verify with `uv run devops ci test tests/roadmap/test_roadmap_refine.py`, which passes before and after.

## 2. Add the premise probe

Reads: `src/devops_cli/roadmap/refine.py`, `tests/support/roadmap_stage.py`. Changes: `src/devops_cli/roadmap/stage_probe.py` (new), `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_probe.py` (new).

- [x] 2.1 Write `tests/roadmap/test_roadmap_stage_probe.py` on a real temporary repository: a present path, a deleted path with its commit, a path that never existed, a defined identifier, `validate_url` removed by a commit, the bound of 10 with the skipped items listed, the extraction rule (a command in backticks, `owner/repo` and `0.41` give no line), and the read-only rule (every command is `cat-file`, `grep` or `log`, and the checkout has no change). Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_probe.py` fails on the base.
- [x] 2.2 Add `stage_probe.py` with `probe_premise(source, sha, body)`, the constants `CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS` (10) and `CONST_ROADMAP_STAGE_PROBE_DEFINITION_LINES`, and the probe messages. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_probe.py` passes.

## 3. Put the probe in the model input

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_probe.py`. Changes: `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [x] 3.1 In `tests/roadmap/test_roadmap_stage_plan.py`, write the test that the request of an issue that cites a tracked file and a function holds `probes` with both lines. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py -k probes` fails on the base.
- [x] 3.2 Call `probe_premise` in `_Planner._request` and add its text under `probes` when it is not empty. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes.

## 4. Return the item on a false premise

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/return_item.py`, `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/commands/roadmap.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_apply.py`, `tests/roadmap/test_roadmap_stage_job.py`, `tests/roadmap/test_roadmap_stage_command.py`, `tests/roadmap/test_roadmap_stage_eval_run.py`.

- [x] 4.1 Write the tests: the replay of #2971 (a temporary repository where a commit removed `validate_url`, a reply with `premise_failed`; the plan holds the item in `returned`, `apply_stage` leaves the issue with the evidence comment and the Status New, and there is no branch and no pull request), a reply with no plan and no `premise_failed` that fails the schema, the counter point `returned`, and the outcome `returned` in the live run of the golden set. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_stage_apply.py tests/roadmap/test_roadmap_stage_job.py tests/roadmap/test_roadmap_stage_eval_run.py` fails on the base.
- [x] 4.2 Add `premise_failed` to `StageProposal` with the validator for the plan fields, `PremiseFailed`, `StagePlan.returned`, `StageApplied.returned`, `StageResult.RETURNED`, the write with `plan_return` and `apply_return`, the report lines and the message of the command, and the outcome `returned` of the live run. Verify that the command of 4.1 passes.

## 5. Ask feasibility to quote the probes

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_kind.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_kind.py`.

- [x] 5.1 In `tests/roadmap/test_roadmap_stage_kind.py`, write the test that the stage prompt names `probes` and `premise_failed` and asks `feasibility` to quote the probes. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_kind.py` fails on the base.
- [x] 5.2 Change the rules and the keys of the prompt: `probes`, the quote in `feasibility`, `premise_failed` and when to set it, and that a thing which no commit removed may be a thing the issue asks to create. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_kind.py` passes.

## 6. Move the false premise out of the pending gates

Reads: `src/devops_cli/roadmap/stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_eval_run.py`. Changes: `src/devops_cli/roadmap/stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_eval_run.py`, the `case.json` files of `tests/fixtures/roadmap_eval/stage/` that record a `false_premise` defect.

- [x] 6.1 Remove `DefectType.FALSE_PREMISE` from `PENDING_GATES`, set `"gate": "none"` on each recorded `false_premise` defect, and change the test `test_a_type_with_no_gate_has_a_count_and_no_rate` to assert the gate `none`. Verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_cases.py tests/roadmap/test_roadmap_stage_eval_gates.py tests/roadmap/test_roadmap_stage_eval_run.py` passes and that `! git grep -n "FALSE_PREMISE: \"#3011\"" src/` finds nothing.

## 7. Document the result

Reads: `docs/TELEMETRY.md`, `src/devops_cli/telemetry/instruments.py`. Changes: `docs/TELEMETRY.md`, `src/devops_cli/telemetry/instruments.py`.

- [x] 7.1 Add the result `returned` to the row of `devops_cli_roadmap_stage_total` in `docs/TELEMETRY.md` and to the description of the counter, and run `uv run devops docs generate --sync-readme`. Verify with `uv run devops docs check`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

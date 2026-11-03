# Tasks

## 1. Refuse a path of the plan's own change folder

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_own_change.py` (new).

- [ ] 1.1 Write `tests/roadmap/test_roadmap_stage_own_change.py` with a group that lists `openspec/changes/3321-plan-check/proposal.md` in `changes`, and `check_proposal(..., change="3321-plan-check")`, and assert one problem that names the path and the own change folder. Add a task code span that names `openspec/changes/3321-plan-check/tasks.md`, and assert one problem that names the group and the path, and add a group that names `openspec/changes/3307-other/proposal.md` and assert no own-change problem
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_own_change.py` fails on the base
- [ ] 1.2 Add `own_change_problems(groups, change)` to `src/devops_cli/roadmap/stage_paths.py`, with the two messages in `MESSAGES.roadmap`; add the `change` keyword to `check_proposal` and call the function there
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_own_change.py` passes
- [ ] 1.3 Pass `change=target.change` from `_settle` in `src/devops_cli/roadmap/stage.py`, and pass `case.change` from `PlanUnderTest.of_case` and `_path_gate` in `src/devops_cli/roadmap/stage_eval_gates.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 2. Refuse a scenario that names code with no behavior test

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_scenario_evidence.py` (new).

- [ ] 2.1 Write `tests/roadmap/test_roadmap_stage_scenario_evidence.py` with a spec scenario whose `then` names `_loki_mode` in a code span and no behavior group's `test` or `verify` names it; assert one problem that names the scenario and `_loki_mode`, and add a scenario that also names `helm template` and assert no problem for it, and add a behavior group whose `test` names `_loki_mode` and assert no problem
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_scenario_evidence.py` fails on the base
- [ ] 2.2 Add `_scenario_problems` to `src/devops_cli/roadmap/stage_change.py`, with the identifier and command span helpers and the message in `MESSAGES.roadmap`, and call it from `check_proposal` after `_delta_problems`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_scenario_evidence.py` passes

## 3. Require a quoted references answer to be covered

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_references.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_reference_coverage.py` (new).

- [ ] 3.1 Write `tests/roadmap/test_roadmap_stage_reference_coverage.py` with `feasibility` that holds `References to 'SingleBinary': files 1, lines 1.` and `tests/commands/k8s/test_k8s.py: 1 (line 12)` and no group or design decision that names the file; assert one problem that names `tests/commands/k8s/test_k8s.py`, and add a decision that names the file and assert none, and add `openspec/changes/archive/2026-10-24-1000-old/proposal.md` to the answer and assert none
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_reference_coverage.py` fails on the base
- [ ] 3.2 Add `_reference_problems` to `src/devops_cli/roadmap/stage_change.py`, with the header and file line expressions and the message in `MESSAGES.roadmap`, and call it from `check_proposal`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_reference_coverage.py` passes

## 4. Replay the plan of PR #3278

Reads: `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `tests/fixtures/roadmap_eval/stage/3167-a-comment-by-a-person-on/case.json`, `tests/fixtures/roadmap_eval/stage/3167-a-comment-by-a-person-on/plan.json`, `tests/fixtures/roadmap_eval/stage/3167-a-comment-by-a-person-on/facts.json`. Changes: `tests/fixtures/roadmap_eval/stage/3278-a-plan-that-names-its-own/case.json` (new), `tests/fixtures/roadmap_eval/stage/3278-a-plan-that-names-its-own/issue.txt` (new), `tests/fixtures/roadmap_eval/stage/3278-a-plan-that-names-its-own/plan.json` (new), `tests/fixtures/roadmap_eval/stage/3278-a-plan-that-names-its-own/facts.json` (new).

- [ ] 4.1 Add the plan of PR #3278 with `change` set to its change folder, and record three defects: the group and the task that name the own change folder with the gate `paths`, the scenario that names `_loki_mode` with no behavior test with the gate `paths`, and `tests/commands/k8s/test_k8s.py` from a quoted `References to 'SingleBinary'` answer with the gate `paths`
  - Verification: `uv run devops roadmap eval stage --dry-run` passes
- [ ] 4.2 Run the replay on the whole set and fix a case until each defect is caught and the good plans still pass
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` passes

## 5. Ask for the rules in the prompt and state the score

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `docs/ROADMAP_WORKFLOW.md`, `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/roadmap/stage_eval_gates.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `docs/ROADMAP_WORKFLOW.md`.

- [ ] 5.1 Add the three rules to `src/devops_cli/ai/tasks/roadmap_stage_change.md`: no path of the own change folder in a group or a task, a behavior test for each scenario that names code unless the scenario names a command, and a group or a design decision for each file of a quoted `References to` answer
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes
- [ ] 5.2 Run `uv run devops roadmap eval stage` with one model before and after the gates, then update the gate counts and the score in `docs/ROADMAP_WORKFLOW.md` and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

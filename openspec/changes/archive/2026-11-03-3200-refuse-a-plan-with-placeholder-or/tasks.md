# Tasks

## 1. Refuse placeholder text, a missing quote and a missing cost

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`, `AGENTS.md`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_content.py` (new).

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_content.py`, assert that `check_proposal` returns a problem that names `why` when `why` is `x`, one that names `existing_tool` when it is `todo`, one that names `feasibility` for a short line, and one for a short decision and a short task, that it accepts `No alternative.`, that it refuses a `feasibility` with no probe line when `probes` is not empty and accepts one that quotes `def f(): pass`, and that it refuses a `builds_own` plan with no token count and no time and accepts `about 80k tokens and 4 hours`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` fails on the base
- [x] 1.2 Add `PLAN_FIELD_MIN_CHARS = 10`, `content_problems(proposal, probes)` and `builds_own` to `src/devops_cli/roadmap/stage_change.py`. Call `content_problems` from `check_proposal`, with a new `probes` keyword. Use `is_placeholder` of `src/devops_cli/roadmap/pull_form.py` for the placeholder rule. Add one message for each refusal to `src/devops_cli/lang/en/messages.py`, each naming its field, and tell the model about `builds_own` and the bound in `src/devops_cli/ai/tasks/roadmap_stage_change.md`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` passes

## 2. Give the job the probe lines

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_probe.py`. Changes: `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [x] 2.1 In `tests/roadmap/test_roadmap_stage_plan.py`, assert that a reply whose `feasibility` quotes no line of the probe that the job built for the item comes back to the model as a refusal, and that a reply that quotes a line is accepted, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [x] 2.2 In `_request` of `src/devops_cli/roadmap/stage.py`, keep the lines of `probe_premise(...)` for the item, and pass them as `probes=` in the `check_proposal` call of `_settle`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 3. Keep the summary whole

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_content.py`, `tests/roadmap/test_roadmap_stage_title.py`.

- [x] 3.1 In `tests/roadmap/test_roadmap_stage_content.py`, assert that `StageProposal` refuses a `summary` that ends with `...`, and in `tests/roadmap/test_roadmap_stage_title.py`, assert that `delivery_title` returns the full summary with no added `...`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_title.py` fails on the base
- [x] 3.2 In `src/devops_cli/roadmap/stage_change.py`, refuse a `summary` that ends with `...` in `_summary_fits_the_title`, and drop `textwrap.shorten` from `delivery_title`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_title.py` passes

## 4. Add the content gate to the replay and record the placeholder plan

Reads: `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_change.py`. Changes: `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `tests/fixtures/roadmap_eval/stage/3167-a-comment-by-a-person-on/case.json` (new), `tests/roadmap/test_roadmap_stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_eval_cases.py`.

- [x] 4.1 In `tests/roadmap/test_roadmap_stage_eval_gates.py`, assert that `gate_for(DefectType.OTHER)` is `GateName.CONTENT`, that `replay_case` marks the `other` defect of the case of #3167 `caught` and its `verify_form` defect `caught`, and that a plan with real text makes the `content` defect `missed`, and raise the case count and the evaluated pulls of `tests/roadmap/test_roadmap_stage_eval_cases.py` for the case, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` fails on the base
- [x] 4.2 Add `CONTENT` to `GateName` in `src/devops_cli/roadmap/stage_eval_cases.py`, and add `_content_gate` and a `Gate(GateName.CONTENT, "#3200", DefectType.OTHER, _content_gate)` entry to `src/devops_cli/roadmap/stage_eval_gates.py`. Add the case of the plan of #3167 (`x` in each text, `true` as the verify command) to the golden set, with one `other` defect with the gate `content` and one `verify_form` defect with the gate `paths`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py tests/roadmap/test_roadmap_stage_eval_cases.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

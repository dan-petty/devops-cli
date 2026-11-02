# Tasks

## 1. Refuse placeholder text and a verify command that cannot fail

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`, `AGENTS.md`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_form.py`.

- [ ] 1.1 In `tests/roadmap/test_roadmap_stage_form.py`, assert that `check_proposal` returns a problem that names `why` when `why` is `x`, that it returns a problem that names `existing_tool` when `existing_tool` is `todo`, that it refuses `true` as the `verify` of a group, and that it accepts a short real sentence and a project verify command, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` fails on the base
- [ ] 1.2 Add `PLAN_FIELD_MIN_CHARS = 10` to `src/devops_cli/roadmap/stage_change.py`. Add `content_problems(proposal)` that refuses a text shorter than the bound in `why`, `existing_tool` and the task texts, calls `is_placeholder` of `src/devops_cli/roadmap/pull_form.py` for the placeholder rule, and refuses the three verify commands. Call it from `check_proposal`. Add one message for each refusal to `src/devops_cli/lang/en/messages.py`, each naming its field, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` passes

## 2. Require a probe quote and a build cost

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_form.py`.

- [ ] 2.1 In `tests/roadmap/test_roadmap_stage_form.py`, assert that `check_proposal(proposal, known, tree, probes=["def f(): pass"])` refuses a `feasibility` list with no quoted probe line, accepts one that holds `The probe shows def f(): pass.`, refuses a `builds_own` plan whose `existing_tool` holds no token count and no time, and accepts `about 80k tokens and 4 hours`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` fails on the base
- [ ] 2.2 Add `probes: Sequence[str] = ()` to `check_proposal` and pass it to `content_problems`. Add `builds_own: bool = False` to `StageProposal`. Match the probe lines as exact substrings after collapsing whitespace, and match a token count and a time in `existing_tool` with two compiled patterns. Add the two messages to `src/devops_cli/lang/en/messages.py`. Add a `probes` field to `PlanUnderTest` and pass it from `_path_gate` in `src/devops_cli/roadmap/stage_eval_gates.py`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` passes

## 3. Keep the full summary in both titles

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 3.1 In `tests/roadmap/test_roadmap_stage_plan.py`, assert that `staging_title` and `delivery_title` return a title that ends with the full summary and holds no added `...`, and that `StageProposal` refuses a `summary` of 41 characters and one that ends with `...`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 3.2 Drop `_ELLIPSIS` and the `textwrap` import from `src/devops_cli/roadmap/stage_change.py`. Build `staging_title` and `delivery_title` from `safe_text(summary)` as it is. Refuse a `summary` that ends with `...` in a field validator of `StageProposal`, and add its message to `src/devops_cli/lang/en/messages.py`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 4. Add the content gate to the replay

Reads: `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_change.py`. Changes: `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`.

- [ ] 4.1 In `tests/roadmap/test_roadmap_stage_eval_gates.py`, assert that `gate_for(DefectType.OTHER)` is `GateName.CONTENT`, that `run_gates` holds the `content` key, and that `replay_case` marks an `other` defect `caught` on a plan with a placeholder in `why`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` fails on the base
- [ ] 4.2 Add `CONTENT` to `GateName` in `src/devops_cli/roadmap/stage_eval_cases.py`. Add `_content_gate`, which calls `content_problems`, and a `Gate(GateName.CONTENT, "#3200", DefectType.OTHER, _content_gate)` entry to `GATES` in `src/devops_cli/roadmap/stage_eval_gates.py`, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` passes

## 5. Record the placeholder plans in the golden set

Reads: `src/devops_cli/roadmap/stage_eval_cases.py`, `tests/roadmap/test_roadmap_stage_eval_cases.py`. Changes: `tests/fixtures/roadmap_eval/stage/placeholder-why/case.json` (new), `tests/fixtures/roadmap_eval/stage/placeholder-verify/case.json` (new), `tests/roadmap/test_roadmap_stage_eval_cases.py`.

- [ ] 5.1 Add one golden-set case for a plan with `x` in `why` and one for a plan with `true` as a verify command. Each case holds the plan, the thinned tree facts and one defect of type `other` with the gate `content` and its message. Raise the case-count assertion of `tests/roadmap/test_roadmap_stage_eval_cases.py` by two, and add the pull numbers of the two recorded plans to its evaluated-pull assertion, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_cases.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

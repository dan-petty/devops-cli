# Tasks

## 1. Refuse a decision with no rejected alternative and an alternative with no fact

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_security.py`, `tests/roadmap/stage/test_roadmap_stage_findings.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_alternatives.py` (new).

- [ ] 1.1 Write `test_content_problems_refuses_a_decision_with_no_rejected_alternative`, `test_content_problems_refuses_an_alternative_with_only_an_opinion`, `test_content_problems_accepts_an_alternative_with_a_fact` and `test_the_plan_that_adds_the_rule_gets_no_problem` first in `tests/roadmap/stage/test_roadmap_stage_alternatives.py`. The base content gate holds no rule for a rejected alternative, and its last text rule is `src/devops_cli/roadmap/stage/stage_change.py:1888:problems.extend(_security_problems(proposal))`, so each of the first three tests fails on the base. The last test builds the plan's own `StageProposal` with one decision and one rejected alternative that cites a line and asserts that `content_problems` returns no problem for it
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_alternatives.py` fails on the base
- [ ] 1.2 Add `_rejected_problems(proposal)` beside `_security_problems` in `src/devops_cli/roadmap/stage/stage_change.py`: it returns one problem when the proposal holds a decision and an empty `rejected` list, and one problem for each rejected alternative whose evidence holds no `path:line`, no quoted command output and no number. Call it from `content_problems` after the security call. Add `stage_problem_no_alternative` and `stage_problem_alternative_fact` to `src/devops_cli/lang/en/messages.py`. The test module also asserts that the design file writes the alternative under `## Rejected alternatives`, and that a proposal with no decision and no alternative gets no problem. Run `uv run devops roadmap eval stage --replay` and state the score before and after the change
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_alternatives.py` passes

## 2. State the rule in the planner prompt, the verification prompt and the design rule

Kind: behavior. Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `openspec/config.yaml`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `openspec/config.yaml`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [ ] 2.1 Write `test_the_stage_prompt_and_the_design_rule_state_the_alternative_rule` and `test_the_verification_prompt_names_the_rejected_alternatives` first in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`; each reads its file and asserts the rule, so each fails on the base. The change adds no reply key, so `test_the_top_level_keys_of_the_reply_are_the_fields_of_the_proposal` of the same module keeps passing
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` fails on the base
- [ ] 2.2 Add to the `rejected` rule of `src/devops_cli/ai/tasks/roadmap_stage_change.md` that a plan with a decision gives at least one rejected alternative under `## Rejected alternatives` and that its evidence holds a `path:line`, a quoted command output or a number. Change the design rule of `openspec/config.yaml` to state the same. Add to `src/devops_cli/ai/tasks/roadmap_stage_verify.md` that the reviewer reads the `rejected` list and returns the `false_premise` finding for a fact that the repository contradicts
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes

## 3. Add the golden-set case of a plan with no rejected alternative

Kind: manifest. Reads: `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `tests/fixtures/roadmap_eval/stage/3247-a-plan-that-changes-security-md/case.json`, `tests/fixtures/roadmap_eval/stage/3247-a-plan-that-changes-security-md/plan.json`, `tests/fixtures/roadmap_eval/stage/3247-a-plan-that-changes-security-md/facts.json`, `tests/fixtures/roadmap_eval/stage/3247-a-plan-that-changes-security-md/issue.txt`, `tests/fixtures/roadmap_eval/stage/split.json`. Changes: `tests/fixtures/roadmap_eval/stage/3168-a-plan-with-no-rejected-alternative/case.json` (new), `tests/fixtures/roadmap_eval/stage/3168-a-plan-with-no-rejected-alternative/facts.json` (new), `tests/fixtures/roadmap_eval/stage/3168-a-plan-with-no-rejected-alternative/issue.txt` (new), `tests/fixtures/roadmap_eval/stage/3168-a-plan-with-no-rejected-alternative/plan.json` (new), `tests/fixtures/roadmap_eval/stage/split.json`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.

- [ ] 3.1 Write `test_the_golden_set_holds_a_plan_with_no_rejected_alternative` first in `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`; it replays the case of pull 3168 and asserts that the content gate catches its one `other` defect, so it fails before the case exists and fails again before the rule of group 1
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` fails on the base
- [ ] 3.2 Create the four files of the case in `tests/fixtures/roadmap_eval/stage/3168-a-plan-with-no-rejected-alternative/`. The plan is the one that pull request 3168 staged for #2877: one group, one decision and an empty `rejected` list, with the null commits and a note that the case reads no commit. Give `facts.json` the tracked files that the plan names, and `issue.txt` the body of #2877. Name one `other` defect at the `content` gate with the message that the new rule gives. Add 3168 to `EVALUATED_PULLS` and raise the counts to 60 cases, 6 good ones and 54 reviewed pulls in `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, raise `JUDGED_BASELINE` to `(83, 320)` in `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, and add the case to half A of `tests/fixtures/roadmap_eval/stage/split.json`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` passes

## Criteria

- Group 1: A test shows that a design with no `## Alternatives` part is refused, and that one with a fact passes.
- Group 1: A test shows that an alternative with no fact (only a sentence of opinion) is refused.
- Group 2: The planner prompt names the part and the rule, and the #3210 test passes.
- Group 3: A replay case from #3163 or #3168 is in the golden set.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

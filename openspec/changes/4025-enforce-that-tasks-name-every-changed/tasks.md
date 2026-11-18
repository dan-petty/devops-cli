# Tasks

## 1. Refuse a plan whose group omits a changed path

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_self_acceptance.py`, `tests/support/builders.py`, `tests/roadmap/implement/test_roadmap_implement_amend.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_group_paths.py` (new).
Adds: `_changed_path_span_problems`

- [ ] 1.1 Write `tests/roadmap/stage/test_roadmap_stage_group_paths.py` first, and let `test_one_omitted_path` fail on the base: it is the case `One omitted path`, a group whose `changes` hold two paths and whose `implementation` names one of them in a code span, and it asserts that `content_problems` names the omitted path. The defective text is `problems.extend(_gate_defect_problems(proposal))`: `content_problems` ends there and reads no code span of a group's `implementation`, so the case fails on the base. Add `test_two_omitted_paths` for the case `Two omitted paths`, `test_every_changed_path_named` for the case `Every changed path named`, and `test_the_plan_of_this_change_passes_the_content_rule`, which builds the plan's own `StageProposal` from a literal and asserts that `content_problems` returns no problem for it
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_group_paths.py` fails on the base
- [ ] 1.2 Add the helper `_changed_path_span_problems` to `src/devops_cli/roadmap/stage/stage_change.py`: it reads the code spans of each group's `implementation` with `code_spans` of `src/devops_cli/roadmap/step_files.py`, and for each group it names the paths of `changes` that no span holds, in one message. Add the message `stage_implementation_missing_paths` to `MESSAGES.roadmap` in `src/devops_cli/lang/en/messages.py`, which names the group and every omitted path. Call the helper from `content_problems`, and write the cases and the self-acceptance case in `tests/roadmap/stage/test_roadmap_stage_group_paths.py`. Run `uv run devops roadmap eval stage --replay` on the base and on the change, and state the score before and after in the pull request comment
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_group_paths.py` passes

## 2. Name both changed paths in the shared plan builder

Kind: other. Reads: `tests/support/builders.py`. Changes: `tests/support/builders.py`.

- [ ] 2.1 Give the default group of `tests/support/builders.py` an `implementation` that names both of its changed paths in a code span, and change no other text. Run `uv run devops ci test tests/roadmap` as the census of the tests that assert a clean plan, and stop when a module outside `tests/support/builders.py` fails
  - Verification: `$ uv run devops ci test tests/roadmap` passes

## 3. State the changed-path rule in the stage prompt

Kind: other. Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [ ] 3.1 State in the task group rules of `src/devops_cli/ai/tasks/roadmap_stage_change.md` that the `implementation` of a group names every path of `changes` in a code span, and assert that sentence with `test_the_prompt_asks_for_each_changed_path` in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Run `uv run devops roadmap eval stage --limit 5` on the base and on the change, and state the score before and after in the pull request comment
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes
- [ ] 3.2 Edit `src/devops_cli/ai/tasks/roadmap_stage_change.md` to state the changed-path rule of a task group
  - Verification: `$ uv run devops ci docs` passes

## 4. Name the changed paths in the first three good stage plans

Kind: manifest. Reads: `tests/fixtures/roadmap_eval/stage/good-2491-a-refused-jwt-exchange-of-the/plan.json`, `tests/fixtures/roadmap_eval/stage/good-2735-the-subprocess-environment-guard-accepts-less/plan.json`, `tests/fixtures/roadmap_eval/stage/good-2739-the-subprocess-environment-guard-accepts-gh/plan.json`. Changes: `tests/fixtures/roadmap_eval/stage/good-2491-a-refused-jwt-exchange-of-the/plan.json`, `tests/fixtures/roadmap_eval/stage/good-2735-the-subprocess-environment-guard-accepts-less/plan.json`, `tests/fixtures/roadmap_eval/stage/good-2739-the-subprocess-environment-guard-accepts-gh/plan.json`.

- [ ] 4.1 The case `good-2491-a-refused-jwt-exchange-of-the` fails first: `uv run devops roadmap eval stage --replay` reports that the content gate refuses the good plan, because a group of `tests/fixtures/roadmap_eval/stage/good-2491-a-refused-jwt-exchange-of-the/plan.json` omits a path of its `changes` from a code span of its `implementation`
  - Verification: `$ uv run devops ci test tests/fixtures/roadmap_eval/stage/good-2491-a-refused-jwt-exchange-of-the` fails on the base
- [ ] 4.2 Give each group of `tests/fixtures/roadmap_eval/stage/good-2491-a-refused-jwt-exchange-of-the/plan.json`, `tests/fixtures/roadmap_eval/stage/good-2735-the-subprocess-environment-guard-accepts-less/plan.json` and `tests/fixtures/roadmap_eval/stage/good-2739-the-subprocess-environment-guard-accepts-gh/plan.json` an `implementation` that names each path of its `changes` in a code span, and change no other text of the plan
  - Verification: `$ uv run devops ci test tests/fixtures/roadmap_eval/stage/good-2491-a-refused-jwt-exchange-of-the` passes

## 5. Name the changed paths in the other three good stage plans

Kind: manifest. Reads: `tests/fixtures/roadmap_eval/stage/good-2950-the-alert-case-is-a-manifest-group/plan.json`, `tests/fixtures/roadmap_eval/stage/good-3264-the-stage-marks-a-plan-ready/plan.json`, `tests/fixtures/roadmap_eval/stage/good-3410-the-stage-gate-proves-a-negative/plan.json`. Changes: `tests/fixtures/roadmap_eval/stage/good-2950-the-alert-case-is-a-manifest-group/plan.json`, `tests/fixtures/roadmap_eval/stage/good-3264-the-stage-marks-a-plan-ready/plan.json`, `tests/fixtures/roadmap_eval/stage/good-3410-the-stage-gate-proves-a-negative/plan.json`.

- [ ] 5.1 The case `good-2950-the-alert-case-is-a-manifest-group` fails first: `uv run devops roadmap eval stage --replay` reports that the content gate refuses the good plan, because a group of `tests/fixtures/roadmap_eval/stage/good-2950-the-alert-case-is-a-manifest-group/plan.json` omits a path of its `changes` from a code span of its `implementation`
  - Verification: `$ uv run devops ci test tests/fixtures/roadmap_eval/stage/good-2950-the-alert-case-is-a-manifest-group` fails on the base
- [ ] 5.2 Give each group of `tests/fixtures/roadmap_eval/stage/good-2950-the-alert-case-is-a-manifest-group/plan.json`, `tests/fixtures/roadmap_eval/stage/good-3264-the-stage-marks-a-plan-ready/plan.json` and `tests/fixtures/roadmap_eval/stage/good-3410-the-stage-gate-proves-a-negative/plan.json` an `implementation` that names each path of its `changes` in a code span, and change no other text of the plan
  - Verification: `$ uv run devops ci test tests/fixtures/roadmap_eval/stage/good-2950-the-alert-case-is-a-manifest-group` passes

## 6. Name the changed paths in the staged compare case

Kind: manifest. Reads: `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/plan.json`. Changes: `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/plan.json`.

- [ ] 6.1 The case `3239-the-toolset-comparison` fails first: `uv run devops roadmap eval stage --replay --cases tests/fixtures/roadmap_eval/staged` reports that the content gate refuses the recorded plan, because a group of `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/plan.json` omits a path of its `changes` from a code span of its `implementation`
  - Verification: `$ uv run devops ci test tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison` fails on the base
- [ ] 6.2 Give each group of `tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison/plan.json` an `implementation` that names each path of its `changes` in a code span, and change no other text of the plan
  - Verification: `$ uv run devops ci test tests/fixtures/roadmap_eval/staged/3239-the-toolset-comparison` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

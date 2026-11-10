# Tasks

## 1. Record the existing tests of a changed module

Reads: `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/support/builders.py`. Changes: `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_paths.py`, write `test_a_behavior_group_that_omits_the_test_of_its_module_is_refused` first, and it fails on the base because `src/devops_cli/roadmap/stage/stage_paths.py` holds no `record_module_tests` and no `existing_test_problems`: the record gives `tests/roadmap/stage/test_roadmap_stage_paths.py` for `src/devops_cli/roadmap/stage/stage_paths.py` from a search that returns it, and the problem names the group, the module and the test. Add the case of a group that names the test, the case of a module with no test, the case of a test that the plan creates, and the case of two groups
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py` fails on the base
- [x] 1.2 Add `record_module_tests` and `existing_test_problems` to `src/devops_cli/roadmap/stage/stage_paths.py`, beside `path_problems`. `record_module_tests` keys each Python module under `src/` that a behavior group changes to the test modules of the tree whose name follows `_TEST_MODULE_PATTERNS` with the stem of the module, plus the test modules that the search gives for the dotted name of the module. `existing_test_problems` reports one problem for each behavior group whose changed module has such a test that the group names nowhere, leaving out every path that a group lists in `creates`. Add the message `stage_problem_missing_module_test` to `MESSAGES.roadmap` in `src/devops_cli/lang/en/messages.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py` passes

## 2. Refuse the group in the paths gate of the plan check

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_self_acceptance.py`, `tests/support/builders.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_module_tests.py` (new).

- [x] 2.1 In `tests/roadmap/stage/test_roadmap_stage_module_tests.py`, write `test_the_paths_gate_refuses_a_group_that_omits_its_module_test` first, and it fails on the base because `check_gates` takes no `module_tests`: it gives one problem under `paths` for a behavior group that changes `src/devops_cli/roadmap/step_files.py` and names no test when the record names `tests/roadmap/implement/test_roadmap_implement_step.py`, and none once the group lists that test. Add `test_the_plan_of_this_change_passes_the_content_rule`, which builds the plan's own `StageProposal`, calls `content_problems` and asserts that it gives no problem
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_module_tests.py` fails on the base
- [x] 2.2 Add the keyword `module_tests` to `check_gates` and `check_proposal` in `src/devops_cli/roadmap/stage/stage_change.py`, pass it in `check_proposal`, and add `existing_test_problems(proposal.groups, tree, module_tests)` to the list of the `paths` gate after `path_problems`. A caller that passes no record judges nothing. Run `uv run devops roadmap eval stage --replay` on the base commit and on the change with the same model, and state the score before and after the change in the pull request comment
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_module_tests.py` passes

## 3. Carry the record through the gate arguments of the job

Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/roadmap/stage/stage_paths.py`, `tests/roadmap/stage/test_roadmap_stage_request.py`. Changes: `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_request.py`.

- [x] 3.1 In `tests/roadmap/stage/test_roadmap_stage_request.py`, write `test_gates_from_request_pass_the_module_tests_through` first, and it fails on the base because `gate_arguments` of `src/devops_cli/roadmap/stage/stage_request.py` takes no `module_tests` keyword: `gate_arguments(_request(), TREE, known=KNOWN, module_tests={MODULE: (MODULE_TEST,)})` returns that record under the key `module_tests`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_request.py` fails on the base
- [x] 3.2 Add the keyword `module_tests` to `gate_arguments` in `src/devops_cli/roadmap/stage/stage_request.py` and return it. In `src/devops_cli/roadmap/stage/stage.py`, record the tests with `record_module_tests(proposal.groups, tree, self._grep)` beside the record of the manifest tests, when `self._grep` is not None, and pass it to `gate_arguments` as `module_tests`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_request.py` passes

## 4. Carry the record through the plan recheck

Reads: `src/devops_cli/roadmap/plan_recheck.py`, `src/devops_cli/roadmap/stage/stage_paths.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/test_roadmap_plan_recheck.py`. Changes: `src/devops_cli/roadmap/plan_recheck.py`, `tests/roadmap/test_roadmap_plan_recheck.py`.

- [x] 4.1 In `tests/roadmap/test_roadmap_plan_recheck.py`, write `test_a_plan_that_omits_the_test_of_a_changed_module_is_refused_by_the_paths_gate` first, and it fails on the base because `_record` of `src/devops_cli/roadmap/plan_recheck.py` passes no `module_tests` to `check_gates`: the recheck of a staged plan whose behavior group changes `src/devops_cli/roadmap/stage/stage_paths.py` and names no test gives one `paths` refusal that names `tests/roadmap/stage/test_roadmap_stage_paths.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_recheck.py` fails on the base
- [x] 4.2 In `src/devops_cli/roadmap/plan_recheck.py`, record the tests with `record_module_tests(proposal.groups, shared.tree, shared.test_search)` beside the record of the manifest tests in `_record`, and pass it to `check_gates` as `module_tests`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_recheck.py` passes

## 5. State the rule of the existing test in the plan-check documents

Reads: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/plan-check.md`. Changes: `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/plan-check.md`.

- [ ] 5.1 Edit the bullet of the `paths` gate in `docs/ROADMAP_WORKFLOW.md` and the gate list of `docs/roadmap/plan-check.md` to state that a behavior group that changes an existing module under `src/` names an existing test of that module, and that a test file that the plan creates is no existing test
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

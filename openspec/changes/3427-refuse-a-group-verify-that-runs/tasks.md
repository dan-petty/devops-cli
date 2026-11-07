# Tasks

## 1. Refuse a verify command that runs a test the group does not name

Reads: `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_form.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_stage_form.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`.

- [ ] 1.1 Add `test_a_verify_command_that_runs_an_unnamed_test_module_is_refused` to `tests/roadmap/test_roadmap_stage_form.py`: a group that changes `src/devops_cli/ai/tasks/roadmap_stage_verify.md` and `tests/roadmap/test_roadmap_stage_verify.py` with `uv run devops ci test tests/roadmap/test_roadmap_stage_task_verification.py` gets one problem that names group 1, the command and the module, and holds the remedy
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` fails on the base
- [ ] 1.2 Add the message `stage_problem_verify_test` to `RoadmapMessages` in `src/devops_cli/lang/en/messages.py`, formatted with `group`, `command` and `path`, and ending with the remedy: list the module in `reads`, or give the command of the group's own test. In `src/devops_cli/roadmap/stage_form.py`, add `_verify_test_problems(number, group)`: skip a command whose first word is `NEGATIVE_SEARCH_WORD`, split the other `verify` command into words with `shlex.split` and fall back to `str.split` when it fails, keep the words that `_is_test_module` accepts as `PurePosixPath`, and return one problem for each kept path that is in none of the group's `changes`, `creates` and `reads`. Call it from `form_problems` beside `_verify_problems`. Add cases for `reads`, `changes`, `creates`, two unnamed modules, a command with no test module, and a negative search that names a test module
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` passes
- [ ] 1.3 Add the rule to the `verify` paragraph of `src/devops_cli/ai/tasks/roadmap_stage_change.md`: a verify test module is one of the group's own `reads`, `changes` or `creates`. Add `test_the_prompt_says_a_verify_command_runs_a_test_the_group_names` to `tests/roadmap/test_roadmap_stage_prompt_rules.py` and assert the sentence
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_prompt_rules.py` passes
- [ ] 1.4 Add the rule to the module docstring of `src/devops_cli/roadmap/stage_form.py`, and run `uv run devops docs generate --sync-readme`
  - Verification: `$ uv run devops ci docs` passes

## 2. Keep the recorded plans and the form tests inside the new rule

Reads: `tests/roadmap/test_roadmap_stage_form.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`, `tests/fixtures/roadmap_eval/stage/good-2491-a-refused-jwt-exchange-of-the/plan.json`. Changes: `tests/roadmap/test_roadmap_stage_form.py`, `tests/fixtures/roadmap_eval/stage/good-2491-a-refused-jwt-exchange-of-the/plan.json`.

- [ ] 2.1 Change the `_plan` helper of `tests/roadmap/test_roadmap_stage_form.py` to take its default `verify` from the case's own test module in `changes`, instead of the sample's `tests/test_sample.py`. Where a case gives a `verify` that names a module the case does not change, add that module to the case's `reads`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_form.py` passes
- [ ] 2.2 Add `tests/github/test_github_app_identity.py` to the `changes` of group 1 in `tests/fixtures/roadmap_eval/stage/good-2491-a-refused-jwt-exchange-of-the/plan.json`, because the `test` task of that group updates the module. Run the golden set replay and make no change to a verdict: a good case that the rule refuses gets its plan corrected
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` passes with no good plan refused
- [ ] 2.3 Run `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py tests/roadmap/test_roadmap_stage_task_verification.py tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_stage_eval_gates.py tests/roadmap/test_roadmap_stage_prompt_rules.py` on the full change, and correct each case that the new rule refuses
  - Verification: the five modules pass

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

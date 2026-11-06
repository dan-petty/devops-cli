# Tasks

## 1. Repeated -e literals in the negative search

Reads: `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_negative_search.py`, `tests/roadmap/test_roadmap_implement_shell_policy.py`. Changes: `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_negative_search.py`, `tests/roadmap/test_roadmap_implement_shell_policy.py`.

- [x] 1.1 Write the failing tests in `tests/roadmap/test_roadmap_implement_negative_search.py`. A search `! git grep -n -e ImagetoolsFake -e inspect_command -e imagetools_recording -e imagetools_runs -- src tests` runs `git grep` with one `-e` for each name, passes on exit 1, and stops with the matching lines on exit 0. A pipe, a shell sign, `-E` or `-P` in an `-e` value is refused, a value that starts with `-` gets the reason that states this rule, and so is an `-e` with no literal, an `-e` followed by `--`, and a word between the last `-e` value and `--`. Remove the `-e name` case from the refusal list
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_negative_search.py` fails on the base, because `read_negative_search` refuses `-e` with "the option `-e` is not allowed"
- [x] 1.2 In `src/devops_cli/roadmap/implement_shell_policy.py`, make `NegativeSearch` hold `literals` and the flag `by_e`, and read the `-e` form in `read_negative_search`. `argv` passes each literal after its own `-e`. Delete the field `literal`, and the comment that refuses `-e`. Add the reasons `search_reason_e_value`, `search_reason_e_dash`, `search_reason_e_forms` to `src/devops_cli/lang/en/messages.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_negative_search.py` passes
- [x] 1.3 Update `tests/roadmap/test_roadmap_implement_shell_policy.py` to the new shape of `NegativeSearch`: the positional form holds one literal in `literals`, and a case reads the `-e` form
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_shell_policy.py` passes

## 2. The stage job checks each literal

Reads: `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/roadmap/stage_move.py`, `tests/roadmap/test_roadmap_stage_form.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/roadmap/stage_move.py`, `tests/roadmap/test_roadmap_stage_form.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [x] 2.1 Write the failing tests `test_each_e_literal_has_its_own_hit_check` in `tests/roadmap/test_roadmap_stage_form.py` and `test_a_move_group_checks_each_e_literal` in `tests/roadmap/test_roadmap_stage_plan.py`. The first gives a group with two `-e` literals, where one has a staged hit and one has none, and expects one problem that names the literal with no hit. The second gives a move group whose second `-e` literal is the bare prefix, and expects two problems that name this literal: the problem of the move and the problem of the created module
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py tests/roadmap/test_roadmap_stage_plan.py` fails on the base, because `read_negative_search` refuses `-e`, so `negative_search_parts` returns None and the stage job checks no literal
- [x] 2.2 In `src/devops_cli/roadmap/stage_form.py`, `record_search_evidence` and `search_problems` check each literal of `NegativeSearch.literals`. In `src/devops_cli/roadmap/stage_move.py`, `_literals` returns the literals, and `move_verify_problems` checks each one
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_form.py tests/roadmap/test_roadmap_stage_plan.py` passes

## 3. The stage prompt names the -e form

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_implement_negative_search.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/test_roadmap_implement_negative_search.py`.

- [x] 3.1 Extend `test_the_stage_prompt_gives_the_options_and_the_signs_that_the_step_reads` in `tests/roadmap/test_roadmap_implement_negative_search.py` to assert that the prompt names the form `-e`, the rule that `--` comes before the paths, and the rule that a literal after `-e` must not start with `-`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_negative_search.py` fails on the base
- [x] 3.2 In `src/devops_cli/ai/tasks/roadmap_stage_change.md`, state the `-e` form in the sentence of the negative search: one literal, or one or more `-e` literals and then `--` before the paths. A literal after `-e` must not start with `-`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_negative_search.py` passes

## 4. The plan of #2610 uses the allowed form

Reads: `openspec/changes/2610-devops-k8s-image-pins-resolves-with/tasks.md`. Changes: `openspec/changes/2610-devops-k8s-image-pins-resolves-with/tasks.md`.

- [x] 4.1 In task 3.3 of `openspec/changes/2610-devops-k8s-image-pins-resolves-with/tasks.md`, replace `-E "ImagetoolsFake|inspect_command|imagetools_recording|imagetools_runs"` with four `-e` literals: `ImagetoolsFake`, `inspect_command`, `imagetools_recording` and `imagetools_runs`. Keep the rest of the line
  - Verification: `uv run devops openspec check` passes

## 5. Document the negative-search form

Reads: `docs/TESTING.md`. Changes: `docs/TESTING.md`.

- [x] 5.1 In the negative-search paragraph of `docs/TESTING.md`, state the form: one plain literal, or one or more `-e` literals with `--` before the paths. A literal after `-e` must not start with `-`. A pipe, `;`, `&&`, a redirect, `-E`, `-P` and any other option stay refused
  - Verification: `uv run devops ci docs` passes

## Workflow follow-up

- #3579 tracks the test over every active plan (acceptance criterion 3 of #3276). This change does not add that test.
- #3596 tracks the step that reads every code span of a Verification line as a command.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

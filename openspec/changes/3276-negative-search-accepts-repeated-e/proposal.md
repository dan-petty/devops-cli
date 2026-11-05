# Proposal

## Why

The negative search of the implement step takes one literal and no `-e` option (#3263). A group that removes several names cannot check them in one command. The plan of #2610 has a group 3 line with `-E` and four names (task 3.3). The step refuses that line with "the option `-E` is not allowed", so the group cannot run (#3276).

## What Changes

- `read_negative_search` in `src/devops_cli/roadmap/implement_shell_policy.py` accepts one or more `-e <literal>` options. Each literal is a plain literal, as the positional literal is. The search takes `--` before the paths when it has `-e` options. The positional literal form stays.
- `NegativeSearch` holds a tuple of literals and a flag that marks the `-e` form. The `argv` of the search passes each literal after its own `-e`. The field of one literal goes away.
- The stage job checks each literal of a negative search. `record_search_evidence` and `search_problems` in `src/devops_cli/roadmap/stage_form.py` and `move_verify_problems` in `src/devops_cli/roadmap/stage_move.py` read every literal.
- `src/devops_cli/lang/en/messages.py` holds three new reasons: an `-e` option with no literal, a word that comes after an `-e` literal, and an `-e` value that starts with `-`.
- `src/devops_cli/ai/tasks/roadmap_stage_change.md` names the `-e` form, and `tests/roadmap/test_roadmap_implement_negative_search.py` asserts it.
- `docs/TESTING.md` states the shape of the `! git grep` form: one plain literal, or one or more `-e` literals and `--`, with the refused tokens.
- Task 3.3 of `openspec/changes/2610-devops-k8s-image-pins-resolves-with/tasks.md` uses four `-e` literals in place of `-E` and the pipe.
- The change fits one pull request. The invariant test of every committed plan is not part of it (see Workflow follow-up).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: A negative search takes one literal or repeated `-e` literals. Each literal keeps the plain-literal rule.
- `roadmap-stage`: The stage job records the hits of each literal of a negative search and checks each one.

## Impact

- Code: `src/devops_cli/roadmap/implement_shell_policy.py`, `src/devops_cli/roadmap/stage_form.py`, `src/devops_cli/roadmap/stage_move.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `docs/TESTING.md`, `openspec/changes/2610-devops-k8s-image-pins-resolves-with/tasks.md`
- Tests: `tests/roadmap/test_roadmap_implement_negative_search.py`, `tests/roadmap/test_roadmap_implement_shell_policy.py`, `tests/roadmap/test_roadmap_stage_form.py`, `tests/roadmap/test_roadmap_stage_plan.py`

## Feasibility

- `git grep` accepts `-e` more than once. A scratch repository at git 2.55.0 gave exit 0 with the matching line for `git grep -n -e alpha -e zzz -- src`, and exit 1 for `git grep -n -e zzz -e qqq -- src`. Exit 1 also holds when the path matches no file (`git grep -n -e zzz -- nothere`).
- The premise holds at origin/main (d254410c). `NEGATIVE_SEARCH_OPTION_LETTERS = "nIFiwlcq"` in `src/devops_cli/roadmap/implement_shell_policy.py` excludes `e`. The test `test_a_negative_search_outside_the_fixed_shape_is_refused_and_starts_no_process` pins `! git grep -e name src/` as refused.
- `read_verification` from `src/devops_cli/roadmap/implement_shell_policy.py` gives the refusal "the option `-E` is not allowed" for the task 3.3 line of #2610. The same reader run over every active `tasks.md` gave 16 refused commands in three plans: #2610 (group 2 prose spans and the `-E` line), #2441 (`helm` and a prose span) and #3187 (`test -z` lines and three `-E` regex lines with boundaries). Only the `-E` lines of #2610 and #3187 are negative searches, and the change fixes only #2610, because #3187 needs a regex that the grammar cannot express.
- Group 2 of #2610 also stops the step before group 3. Its verification line holds prose code spans (`tagged_image`, `nginx:1.27`) that the step reads as commands. That cause is outside this change.

## Existing Tool Considered

`git grep` covers the search. It matches any of several `-e` patterns in one command, so the change keeps git as the program that searches. Git has no option policy: it accepts `-E`, `-P` and a regex pattern. The step keeps its allowlist and its plain-literal check, and it requires `--` before the paths when `-e` is used. The change builds no search engine. The grammar in the step adds about 40 lines.

Internal code that the change deletes: the one-literal field of `NegativeSearch` (`literal`), the comment that refuses `-e` (`implement_shell_policy.py`, lines 150-151), the refusal case `! git grep -e name src/` in `tests/roadmap/test_roadmap_implement_negative_search.py`.

## Dependencies

- #3263 added the negative search. The change extends it.
- The plan of #2610 is edited in this change. #3490 also lists #2610, so its edit of that plan must follow this change or merge into it.

## Workflow follow-up

- #3579 tracks the test over every active plan (acceptance criterion 3 of #3276). This change does not add that test. After this change, 15 refused Verification commands remain in three active plans, and #3579 holds the list.
- #3596 tracks the step that reads every code span of a Verification line as a command (`src/devops_cli/roadmap/step_files.py`).

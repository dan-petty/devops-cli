# Proposal

## Why

The implement step runs each `Verification:` command of a plan as a list of words, never through a shell. The function `read_verification` in `src/devops_cli/roadmap/implement_shell_policy.py` accepts a fixed grammar, and it refuses everything else. Two active plans hold lines that it refuses, and no test reads the active plans against it (#3595, #3579).

- The plan of #3187 holds `test -z "$(find ...)"` lines (the program `test` is not in the verification list) and `! git grep -n -E ...` lines (the option `-E` is not in the grammar of the negative search). It holds 9 refused commands in 8 tasks.
- The plan of #2610 holds code spans in the prose of the `Verification:` line (`tagged_image`, `nginx:1.27`, `resolve_image` and `docker buildx`). The step reads every code span of the line as a command, so it refuses these 4 spans.

A plan with a refused line stops the implement step at its group. The stage gate does not find it, because it reads the first command of a task only (#3579).

#3595 asks for the rewrite of these plans and a test. #3579 asks for the same test with an exception list. The two issues describe one invariant test in `tests/invariants/test_change_folders.py` over every active `tasks.md`. Two pull requests would add the same test function to one file and conflict on merge, so one pull request delivers both and carries `Closes #3595` and `Closes #3579`.

## What Changes

- `tests/invariants/test_change_folders.py` gains `test_every_verification_line_of_an_active_plan_is_accepted_by_the_step`. It reads the `tasks.md` of every active change folder, skips `openspec/changes/archive/`, and sends every code span of every `Verification:` line of every task to `verification_problem`, which calls `read_verification`. The test holds no copy of the grammar. A failure names the path, the line and the command.
- The test reads the tasks with `parse_task_groups`, the function that the implement step calls, so the test and the step see the same spans. It does not use the plan reader `read_change`, which reads one command for each task and raises on a bad plan.
- The plans of #3187 and #2610 are rewritten so that the step accepts each `Verification:` line and the line keeps its check (see `design.md`).
- No exception list. The two issues differ here: #3595 asks for a rewrite, and #3579 asks for a list of accepted exceptions with a stale check. This change takes the rewrite. Every refused line can be written in the grammar, so the list would hold no entry, and an empty list is dead code that a person must keep.
- This change alters no behavior that a consumer observes: it edits a test and the text of two plans. It sets `skip_specs: true`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: `tests/invariants/test_change_folders.py`.
- Plans: `openspec/changes/2610-devops-k8s-image-pins-resolves-with/tasks.md` and `openspec/changes/3187-group-the-job-modules-in-subpackages/tasks.md`. Their owners review the new lines in this pull request.
- Documents: none state the rule that the test holds.

## Feasibility

- Command output confirms the premise at `origin/main`. A script that sends each `Verification:` code span of each active `tasks.md` (found with `parse_task_groups`) to `verification_problem` reports 13 refused spans: 4 in `2610-devops-k8s-image-pins-resolves-with` (`tagged_image`, `nginx:1.27`, `resolve_image`, `docker buildx`) and 9 in `3187-group-the-job-modules-in-subpackages` (6 `test -z` spans in tasks 1.1 to 5.1 and 8.1, and 3 `-E` searches in tasks 6.1, 7.1 and 8.2).
- The other folders that #3579 names (2147, 2184, 2570, 2592, 2644, 3373) are archived or hold no refused span. The same script reports no refusal for them. The folder of #2441 is archived. The `-E` line of #2610 that #3276 meant to fix is already accepted at `origin/main`.
- The grammar was read in `src/devops_cli/roadmap/implement_shell_policy.py`. The negative search accepts the options `-n -I -F -i -w -l -c -q`, one or more `-e` literals of plain characters, and relative paths of plain characters. `read_verification` accepts the programs `git`, `uv`, `ruff`, `mypy`, `grep`, `cat`, `ls`, `head`, `tail`, `find`, `openspec` and `devops`. The `-E` option, the `test` program and a pathspec with `:` are refused. These facts decide the rewrite.
- `parse_task_groups` in `src/devops_cli/roadmap/step_files.py` gives the code spans of every `Verification:` line of every task of a numbered group, and the zero-based line of the task. The step calls it. The test calls it too.
- `tests/invariants/test_change_folders.py` already walks the active folders and skips `archive/` in `tree_problems`. The new test uses the same rule.
- `devops ci fail-to-pass --base origin/main` proves the test: it fails on the plans of the base and passes after the rewrite.

## Existing Tool Considered

No open, maintained tool or library covers the need. The rule is the grammar of `read_verification` of this repository, and no linter reads an OpenSpec `tasks.md` against it. The change reuses `parse_task_groups` and `verification_problem`, and it uses `pytest` and `markdown-it-py`, which the repository already has. It adds one test function and a helper of about 25 lines, and it deletes no code. Cost: about 20,000 tokens to build, about 2,000 tokens a year to keep, and about 2 hours.

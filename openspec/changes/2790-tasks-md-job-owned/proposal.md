# Proposal

## Why

Issue #2790. An implement step that edits `tasks.md` beyond its own checkboxes stops, and the job discards correct code. Job `devops-cli-runner-20261030-170945-1b28` ran #2745. The agent fixed `_write_content` and `_copy` and added tests for both. The step stopped with "Group 2 changed. A step may change only its own group." The discarded diff shows that the agent ticked every task of groups 1 and 2, and that it deleted the number "2.3" from the third task of group 2.

The job reads the verification commands from the text of `tasks.md` before the run. No edit of the file can change which command judges the work. The file is the bookkeeping of the job, and a model edit of it is no reason to stop. Three changes (#2767, #2774, and the stop on the other groups) each restored one part of the file and kept a stop for the rest. This change makes one rule of them.

## What Changes

- After each turn of the model, the step writes `tasks.md` back to its text before the run, and applies only the checkboxes of its own group that the agent ticked. Every other edit is undone: a task text, a heading, a command, a bullet, an added or removed group, a reordered task, and a line outside every numbered group.
- The step never stops because of an edit of `tasks.md`. The checks that remain are the verification commands from the text before the run, the static checks, and the unticked-task check for the own group. The tick turn of #2721 stays, and its rule that it may change only `tasks.md` stays: that rule is about files.
- When the agent changed the file, the step prints one line to the error stream that names the change whose file it restored. A tick of the own group and nothing else prints no line.
- A fix step ticks no task. Its edit of `tasks.md` is undone the same way, and the step goes on.
- The step reads the ticks of the own group by position. When the agent changed the number of the tasks of its group, the position of a tick means nothing, so the step reads none. The unticked-task check then gives the tick turn, and then stops with the first unticked task named.
- The code of `_tasks_failure`, `_whole`, `_shape`, `_same_tasks`, `_restored_wrong`, `_restore_ticks`, `_restore_own_text`, `_own_group_failure`, `_other_groups_failure` and `_fix_tasks_failure` goes. So do `_region_bounds`, `TaskGroup.first_line`, `StepInputs.region` and `StepInputs.groups`. The messages `implement_stop_group_changed`, `implement_stop_tasks_edited`, `implement_stop_fix_tasks_changed`, `implement_restored_ticks` and `implement_restored_text` go. One message for the note comes in.
- The prompt says that the job writes the whole file back and keeps only the ticks of the group.
- This change covers #2779, an edit outside every numbered group that reaches the commit. The whole file is written back, so no such edit reaches the commit. #2779 stays open until a person closes it.
- The ruff format stop of the job for #2656 is a static check on code that the agent wrote. It judges the work, and it stays.
- A consumer observes the exit checks of a step, so the change carries a spec delta. It modifies three requirements of `roadmap-implement-step`, removes three and adds one.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`: one requirement writes `tasks.md` back and applies the ticks of the own group. The exit checks, the fix step and the tick turn follow it.

## Impact

- `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
- `tests/test_roadmap_implement_step.py`, `tests/test_roadmap_implement_step_ticks.py`, `tests/test_roadmap_implement_step_own_text.py`.
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

- The failure is real. The stop comments of the Service on #2745 (04:18 and 17:14 UTC, 2026-10-30) read "Group 2 changed. A step may change only its own group." The issue text holds the diff: the third task of group 2 changed from `- [ ] 2.3 , run ...` to `- [x] , run ...`.
- The cause is in `implement_step.py`. `_other_groups_failure` compares the other groups with `_shape`, which holds the title and the text and the commands of each task. It stops on any difference, and it restores only the checkboxes (#2767). `_own_group_failure` stops on a change of the number, the order or the heading of the own tasks (#2774). `_tasks_failure` calls both.
- The commands are read before the run. `build_step_inputs` parses `tasks.md` once, and `_exit_failure` runs `_verification_failure(source, inputs.group)` with that group. A test of this change keeps this true: the agent rewrites a command, and the original command runs.
- The parser gives what the restore needs. `parse_task_groups` gives the zero-based line of each task, and `_file_lines` splits the text as markdown-it does, at `\n`, `\r` and `\r\n`. The old tests for CRLF and lone CR keep running against the new code.
- `implement_stop_group_changed`, `implement_stop_tasks_edited` and `implement_stop_fix_tasks_changed` have no use outside `implement_step.py`. A search of `src` and `tests` shows this.

## Existing Tool Considered

The step already uses `markdown-it-py` through `parse_task_groups`. The change reuses it for the lines of the tasks of the own group, and reuses `_file_lines` for the split. It builds no parser. The change builds only the replacement of a checkbox on a line of the text from before the run. The model writes no part of the text that the job commits, so nothing needs to be compared after the write.

Cost of what it builds, estimated: about 40 lines of code and 120 lines of tests, about 60k tokens of agent work and two hours of elapsed time. The change deletes about 190 lines of code and the tests of the stops. The upkeep is smaller than before: one rule replaces three.

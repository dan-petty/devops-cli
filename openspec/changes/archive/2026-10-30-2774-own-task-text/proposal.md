# Proposal

## Why

Issue #2774. An implement step that edits the text of its own tasks in `tasks.md` stops, and the job discards all its work. The runner Job for #2656 ran about 30 tool calls and wrote a fix and a test. It stopped with "The tasks of group 1 changed. A step may only tick them." The discarded diff shows that the agent rewrote the text of task 1.1: the staged plan named `tests/test_round_trip.py` for the test, the agent wrote the test in another file, and it changed the task to match.

The rule protects a real thing. A model must not weaken the verification command of its own task. But the stop costs a whole step of correct work for an edit of text, and the job can protect the command without the stop: it already reads the commands from the tasks as they were before the run.

## What Changes

- After each turn of the model, the step compares its own group with its text before the run. When the number of the tasks, their order or the heading of the group differ, the step stops, as today. When only the text of the group differs, the step writes the text of the group from before the run back to `tasks.md`, keeps the checkbox state that the agent set, and goes on. It prints one line to the error stream that names the group.
- The verification commands stay those of the text before the run. A command that the agent rewrote to pass does not run. The original command runs. When it fails, the stop reason names the original command and holds its output, for example the error of a test file that does not exist.
- A fix step keeps its rule: it may change no task.
- The prompt says: do not edit the text of a task. If the path that a task names is wrong, write the file at that path anyway, or say in the last message why you did not.
- The restore reuses `_restore_ticks`, the parser and the line numbers of #2767. `TaskGroup` gets the fields `first_line` and `end_line`, left out of its comparison, to cut the group out of the file.
- A consumer observes the exit checks of a step, so the change carries a spec delta. It modifies two requirements of `roadmap-implement-step` and adds one.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`: the exit check for the own group restores its text and stops only on a change of the number, the order or the heading of its tasks. One requirement is added: the step writes the text of its own group back.

## Impact

- `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `src/devops_cli/lang/en/messages.py`.
- `tests/test_roadmap_implement_step_ticks.py`, `tests/test_roadmap_implement_step.py`.
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

- The failure is real. The stop comment of the Service on #2656 at 13:14 UTC reads "The tasks of group 1 changed. A step may only tick them." Its diff of the discarded work changes the text of task 1.1 from `tests/test_round_trip.py` to `tests/test_round_trip_merge_key.py`, in the task and in the command after "verify that". The diff also holds the real fix in `src/devops_cli/config/round_trip.py`.
- The cause is in `_tasks_failure` of `implement_step.py`. It compares the own group with `_shape`, which holds the title and the text and the commands of each task, and it stops on any difference. The other groups use the same `_shape` and then restore their checkboxes (#2767).
- The commands are read before the run. `build_step_inputs` parses `tasks.md` once, and `_exit_failure` runs `_verification_failure(source, inputs.group)` with that group. A test of this change keeps this true: it rewrites the command, and the original command runs.
- The parser gives what the restore needs. A probe of `parse_task_groups` shows the zero-based line of each task and the first line of each group heading. The end line of a group is the first line of the next `##` heading, or the end of the file. With both lines the step can replace the lines of one group and keep the line ends of the file.
- The task text of a staged plan holds its verification command in the task line, not in a `Verification:` line, as in #2656. Such a command is a code span of the task text. The step runs only the commands of `Verification:` lines. This change does not change that rule.

## Existing Tool Considered

The step already uses `markdown-it-py` through `parse_task_groups`. The change reuses it for the lines of the group, and reuses `_restore_ticks` for the write of the checkboxes. The change builds only the replacement of the lines of one group by their text before the run, with the file's own line end. After the write the step parses the file again and compares the group with the text before the run. A write that failed to restore the group stops the step. No new library is needed.

Cost of what it builds, estimated: about 50 lines of code and 150 lines of tests, about 70k tokens of agent work and two hours of elapsed time. The upkeep is small: the code follows the parser.

The change deletes no code. It replaces the stop on an edit of the own group with the restore.

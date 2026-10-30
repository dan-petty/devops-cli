# Proposal

## Why

Issue #2767. An implement step that ticks the tasks of a later group loses all its work. The Service ran the step for group 1 of the change of #2745. The agent wrote the fix and two test files, and it ticked the tasks of group 1 and of group 2 in `tasks.md`. The step stopped with "Group 2 changed. A step may change only its own group.", reset the checkout, and kept nothing.

A tick is bookkeeping that the job owns. A model that did more than its group did nothing unsafe: a later group verifies its own work in its own step. The rule costs a whole step of correct work for a checkbox.

## What Changes

- After each turn of the model, the step compares every other group with its base. A group that differs only in its checkboxes gets its checkbox state written back to the base state in `tasks.md`. The step prints one line to the error stream, which the Job log holds, that names the restored groups. Then it goes on with the checks of its own group.
- Any other difference in another group still stops the step: the title, the text of a task, a verification command, a task or a group added or removed, and any other line of the group, such as a changed bullet or an added paragraph. After the restore the text of the group must equal its text before the run.
- A `tasks.md` that holds one group number twice stops the step, and a change whose base `tasks.md` holds one is refused before the step starts. Without this, a copy of a group could hide an edit of it.
- The step splits the file into lines as the parser does, at `\n`, `\r` and `\r\n`, so a line number of the parser always indexes the right line.
- The restore runs after the first turn and after the extra turn for the ticks (#2721). Every exit check reads the restored file, and the step stages the files after the restore, so the commit holds the restored `tasks.md`.
- The own group keeps its rule: its checkboxes may change and its text may not. A fix step keeps its rule: it may change no task.
- The prompt of the step says: tick only the tasks of your group, because a later group runs in its own step and ticks its own.
- The step now reads the line of each task from the parser, to write one checkbox back. `GroupTask` gets a `line` field that is left out of its comparison.
- A consumer observes the exit checks of a step, so the change carries a spec delta. It modifies two requirements of `roadmap-implement-step` and adds two.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`: the exit check for other groups, and the extra turn, stop on a change beyond the checkboxes. Two requirements are added: the step restores the checkboxes of the other groups, and a change beyond the checkboxes stops the step.

## Impact

- `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`, `src/devops_cli/lang/en/messages.py`.
- `src/devops_cli/lang/en/help.py` and the documents that `devops docs generate --sync-readme` writes from it.
- `tests/test_roadmap_implement_step.py`, `tests/test_roadmap_implement_step_ticks.py` and `tests/support/implement_step.py`.
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

- The failure is real. The stop comment of the Service on #2745 reads "Stopped at group 1. Reason: Group 2 changed. A step may change only its own group." Its diff of the discarded work changes `- [ ]` to `- [x]` for tasks 1.1 to 1.3 and for tasks 2.1 to 2.3 of `tasks.md`, and holds the real fix in `settings.py` and `write_history.py`.
- The cause is in `_tasks_failure` of `implement_step.py`. It compares every other group with `_whole`, which holds the title and the tasks with their checkboxes, and it names the first group that differs. The own group uses `_shape`, which leaves the checkboxes out. So a tick in another group is the only change that is allowed in the own group and stopped in another group.
- The run loop in `implement_run.py` parses `tasks.md` once, before the first step, and runs a step for each group that is not fully ticked. A group that the step restored as unticked stays in that list and runs in its own step. A later step whose work is already in the checkout runs its verification commands, finds them passing, and ticks its tasks.
- The parser gives the line of a task. A probe with `markdown-it-py` 4.2.0 on a `tasks.md` with CRLF line ends shows that the `map` of the first inline token of each top-level list item holds the zero-based line of the task, also for a nested `Verification:` line and for an ordered list. The step can write one checkbox back without a parser of its own.
- The commit holds the restored file. `_exit_failure` stages the checkout after `_tasks_failure`. The last call of `_exit_failure` before the commit runs after the extra turn, so a tick that the extra turn adds to another group is restored before the files are staged.

## Existing Tool Considered

The step already uses `markdown-it-py` through `parse_task_groups`. The change reuses it: the parser gives the shape of a group, its checkbox state and now the line of each task. The change builds only the write-back of one checkbox, which replaces the first `[ ]`, `[x]` or `[X]` of a line. After the write the step parses the file again and compares each restored group with its base. A write that failed to restore a group, or that left any other difference in its text, stops the step. No new library is needed.

Cost of what it builds, estimated: about 60 lines of code and 150 lines of tests, about 60k tokens of agent work and two hours of elapsed time. The upkeep is small: the code follows the parser.

The change deletes no code. It replaces the stop on a tick of another group with the restore.

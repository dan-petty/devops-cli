# Design

## Decisions

- **The job restores, the model does not decide.** A tick says that the work of a task is done. The group of that task verifies its work in its own step. So the tick of a step for another group carries no fact that the job can use, and the job writes the base state back. The model loses nothing: its work for the own group stays in the commit.
- **Compare the shape, then restore the checkboxes.** For each other group the step compares `_shape` (the title, the text of each task without its checkbox, and its verification commands) of the base with the group after the run. A difference stops the step with the group named, as today. When the shapes match and the groups still differ, only the checkboxes differ. The step restores them. This reuses `_shape`, which the own group already uses.
- **One restore for every turn.** `_exit_failure` runs after the first turn and after the extra turn for the ticks. The restore is part of `_tasks_failure`, which `_exit_failure` calls first, so both turns get the same rule. A model that ticks another group in the extra turn is restored again. The extra turn may still change only `tasks.md`, which `_foreign_change` checks against the tree after the first restore.
- **The restore runs before the files are staged.** `_exit_failure` calls `_tasks_failure` before `_stage`, and the commit takes the staged files of the last call. So the commit holds the restored file and never the file of the model.
- **Restore a checkbox by its line.** `GroupTask` gets a `line` field, the zero-based line of the task in the file, read from the `map` of the parser token. The field is left out of the comparison, so a blank line that moves a task is not a difference. The restore splits the file at `\n` only, replaces the first checkbox marker of each line that differs, and joins the lines again. A file with CRLF line ends keeps them: the step reads and writes with `newline=""`.
- **A restore is checked.** After the write the step parses the file again and compares each restored group with its base. A group that still differs stops the step as changed. A wrong line number can then never reach a commit.
- **The own group keeps its rule.** Its checkboxes may change, its text may not. The extra turn asks for the ticks of the own group only.
- **A fix step keeps its rule.** It may change no task, checkboxes included. It restores nothing.
- **The log line.** The restore logs one `info` line with the numbers of the restored groups. The text is in `MESSAGES`.
- **The prompt.** It says to tick only the tasks of the own group, and why: a later group runs in its own step and ticks its own. The prompt is a request, and the restore is the check.

## Rejected alternatives

- **Stop as before and fix the prompt only.** The first live run shows a model that did more than its group, and the stop cost a whole step. A prompt is a request, not a check, and AGENTS.md rule 2 asks for a check.
- **Accept the ticks of a later group.** The tick would claim that the work of that group passed its verification. No check ran for that group. The run loop would skip the group (it skips a ticked group), and its verification would never run.
- **Restore the whole text of a group from the base.** It is simpler, but it also hides a change of prose that the step does not judge. It would change what the step accepts, beyond the checkboxes.
- **Restore with a regular expression over the whole file.** It would be a second parser of the task list. The parser gives the line of each task.
- **Reset only `tasks.md` to the base after the run.** The own group needs its ticks, and the step would have to write them again.
- **Restore in the run loop after the step.** The step has committed by then. The commit would hold the file of the model, and a second commit would be needed.

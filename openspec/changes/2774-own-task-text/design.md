# Design

## Decisions

- **The job owns the text of the tasks, as it owns the ticks.** A task text is a plan that the job staged. The model does its work in files and reports in its last message. A rewrite of the text carries no fact that the job can use, and the job writes the text from before the run back. The model loses nothing: its work for the group stays in the commit.
- **The commands are those of the text before the run.** The step runs `_verification_failure` with `inputs.group`, which `build_step_inputs` read before the first turn. The restore does not change this. A model that rewrites a command to one that passes gains nothing: the original command runs and its failure names it.
- **The structure still stops the step.** The step stops when the number of the tasks differs, when the tasks are the same texts in another order, or when the heading differs. A model that removes a task would otherwise skip its verification, and a model that moves a task would put its tick on another task.
- **Order is judged by the task texts.** A permutation of the texts of the tasks, not equal to their order before the run, is a reorder. A rewrite that also reorders cannot be told from a rewrite, and the restore by position makes it harmless: each task gets the text and the tick state of its position.
- **Restore the whole group, then the ticks.** The step writes the lines of the group before the run in place of the lines of the group after it, with the line end of the heading. Then it parses the file and checks that the group equals its text before the run. Then it writes the checkboxes that the agent set with the same code that restores the ticks of other groups. The text of the group is never built by a second parser.
- **Cut the group out by line.** `TaskGroup` gets `first_line` and `end_line`, left out of its comparison like `GroupTask.line`. They come from the headings that the parser already reads.
- **One restore for every turn.** The restore is part of `_tasks_failure`, which `_exit_failure` calls first, so the first turn and the extra turn for the ticks (#2721) get the same rule. The file is written before the files are staged, so the commit holds the restored file.
- **The note goes to the console stream.** One muted line names the group, as for the restore of other groups (#2767). A tick of the group and nothing else prints no line.
- **A fix step keeps its rule.** It may change no task, checkboxes included.
- **The prompt.** It says not to edit the text of a task, and what to do with a wrong path. The prompt is a request, and the restore is the check.

## Rejected alternatives

- **Stop as before and fix the prompt only.** The live run shows a model that edits a text that does not fit its work. A prompt is a request, not a check, and AGENTS.md rule 2 asks for a check.
- **Accept the edited text.** The model could then weaken the command of its own task. The step runs the commands from the text before the run, and the committed text would no longer say what judged the work.
- **Run the commands of the edited text too.** The step would run a command that the model chose. Its pass proves nothing about the plan.
- **Check the named paths of the plan in the step.** The stage job can flag a path that does not exist (#2772). This item adds no such check.
- **Restore only the first line of each task.** A task has a `Verification:` line and the model can edit it. The whole group text is the unit that is compared and restored.
- **Replace the group by a regular expression over the file.** It would be a second parser of the task list. The parser gives the lines of the group.

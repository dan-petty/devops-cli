# Design

## Decisions

- **The job owns `tasks.md`.** The job staged the plan, and it reads the commands from the plan as it was. The model does its work in files and reports in its last message. An edit of the file carries no fact that the job can use. The job writes the text from before the run back and loses no work: the work of the model is in the other files.
- **One restore for the whole file.** The step takes the raw text of `tasks.md` from before the run, which `build_step_inputs` reads with `newline=""`. It sets the box of each own task that the agent ticked, and writes the result. The rest of the file is that text, byte for byte. So a heading, a bullet, a trailing space, a line end and a section outside every group are those of before the run. This covers #2779.
- **Ticks are read by position.** The own group in the file after the run gives its tasks in order. When their number equals the number of the tasks before the run, the task at a position is ticked if the agent ticked the task at that position. A rewritten text is no difference. A group that the agent ticked partly keeps its unticked tasks unticked, and the unticked-task check handles them.
- **A tick only adds.** The result for a task is ticked if it was ticked before the run or the agent ticked it. An agent that unticks a task of a done group changes nothing.
- **No ticks when the number differs.** An agent that adds or removes a task of its group makes the position of a tick meaningless. The step reads no tick. The group then has unticked tasks, and the existing check gives the tick turn and then stops with the first unticked task named. The reason is about the work that the group lacks, not about an edit of the file.
- **A repeated group number.** The step reads the ticks from the first group with the own number. The text of the file is never used for anything else, so a copy of a group can hide nothing. A file with a repeated number before the run is refused before the step starts, as before.
- **A fix step reads no ticks.** Its restore writes the text from before the run and applies none. The fix step ticks nothing, by restoring.
- **Every turn.** The restore is called from `_exit_failure`, where `_tasks_failure` was. The first turn and the tick turn (#2721) get the same rule. The file is written before the files are staged, so the commit holds the restored file. The tick turn still may change no file but `tasks.md`; `_foreign_change` judges files, not the text of `tasks.md`.
- **A file that is gone or not UTF-8.** The step reads the file as the run left it. A missing file or a file that is not UTF-8 text has no ticks, and the write replaces it. A path of `tasks.md` that is a link is removed before the write, so the write never goes through a link.
- **The note.** One muted line to the error stream names the change whose `tasks.md` the step restored. It prints only when the bytes of the file differ from the restored text.
- **The commands.** The step runs `_verification_failure` with `inputs.group`, which the step read before the first turn. This does not change.
- **The prompt.** It says that the job writes the whole file back and keeps only the ticks of the group. The prompt is a request. The restore is the check.

## Rejected alternatives

- **Keep the stops, and widen the restore a little more.** Three changes did this and each left a stop. The next edit, such as a deleted number, hit a stop again. The evidence is the stop of the job for #2745, after #2767 and #2774.
- **Read ticks by task text.** An agent that rewrites a text and ticks it would lose the tick. Rewrites are common, as #2774 shows.
- **Read ticks for the tasks that match by position and ignore the rest.** When the number differs, the match has no basis. A tick that lands on the wrong task is worse than a tick that is missing.
- **Copy the checkbox state of the agent, so an untick works.** An untick of a done task has no use for the job, and it would turn a done task into a stop.
- **Compare the file after the write.** The text is built from the text before the run and one box per tick. A comparison would test the code against itself.
- **Make the job run `ruff format` for the agent.** The ruff stop of #2656 is not an edit of `tasks.md`. It belongs to another item.

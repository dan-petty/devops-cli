# Design

## Decisions

- **One function names a text in a reason.** `shown(text, limit)` escapes (`unicode_escape`) and cuts. The step names the command with it at the one place where `commands_failure` builds the name, and every message of that function reads that name. The gate does the same in `_verify_problem`. The job posts `outcome.reason` as it is, and the escape keeps the text ASCII with no control character, so no second escape in `implement_run` is needed. Rejected: `safe_text` in `implement_run.stop` alone. It would leave the gate and the other readers of the reason open, and it joins the lines of the reason.
- **The rule of the classifier follows the message.** `failure.py` builds its pattern from `implement_stop_command_refused` with the two fields replaced by `.*`, so a change of the text changes the rule, and a test reads the class from the real message. Rejected: a typed field in `StepOutcome`. It needs a change of the record, the comment and the job for one class.
- **A refused verification command is `refused_tool`.** It was `refused_tool` / `wait` for a one-word program on the base, and the plan needs a person to change the command. `plan_defect` / `amend` would fit as well, but it would change the class of the base for the case that worked.
- **The plan-time check reads the reader of the step.** `as_path` leaves a word with no `/` alone, by design, because a search pattern is such a word. A negative search is different: its paths are known for sure. So `_verify_paths` takes them from `read_negative_search`, and `.` is skipped. The check runs at the staged commit, so a folder that the group deletes is still there. Rejected: a rule in the step that a path must match a tracked file at the start. The step has no start commit at the check, and the plan-time check covers the case.
- **The limit is on the words of every verification command.** It is in `read_verification`, before the first word is read. `execve` fails at 131072 bytes for one argument, and the corpus has no command over 414 characters.
- **The log does not name `!`.** The words after it are free text. The row `!` stays in the table of refusals, and the log says `other` for it.
- **The deferral of several names is #3276.** The shape keeps one literal. The corpus shows that the issue needs three more parts: repeated `-e`, a literal with quotes or parentheses (3091, 3208), and the prose code spans of #2610. The rewrite of the plan of #2610 is a separate plan fix, because its refused lines are not searches.

## Rejected alternatives

- **Show the raw command and escape it in the job.** Two places would need the same rule.
- **Catch `OSError` for a verification command.** A command that cannot start is a defect of the plan, and the limit gives the reason before the process starts.

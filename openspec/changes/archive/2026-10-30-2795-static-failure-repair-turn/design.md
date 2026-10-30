# Design

## Decisions

- **The repair turn is the tick turn with another message and another set of paths.** Both turns continue the conversation, run under the same limits, compare the tree before and after, and run every exit check again. One helper holds that shape. The tick turn passes only `tasks.md` as the path it may change. The repair turn passes the paths that the step had changed before the turn, plus `tasks.md`.
- **The turn may change only files that the step already changed.** An unused import is fixed in a file the agent wrote. A fault that needs a change in a file the step never touched is a second fix on a fix (AGENTS.md rule 2). The step stops for it, and names the paths, bounded as for the tick turn.
- **Only a static fault gets the turn.** The issue asks for `ruff check` and `mypy --strict`. A failed verification command can have any cause, such as a test that fails for a reason in the design. It keeps today's stop. The exit checks report which kind of check failed, so the choice does not read the text of the reason.
- **One extra turn in total.** A step that has a static failure and an unticked task gets one turn. Its message holds the failure text and the list of the unticked tasks, so the model can fix both in the same turn. After the turn the checks run again. If the tick is still missing, the step stops with the unticked task. A tick turn does not follow. A second turn would pay again for a model that failed the first ask, and the budget of a step stays bounded: the same `UsageLimits` cap both turns. The tick turn that runs first cannot start a repair turn after it. A step never has two extra turns.
- **The step stops with the first check that fails after the turn.** The exit checks run again from the start. The reason names the first check that fails in that run, which is the state of the checkout that the diff in the stop comment shows. The reason of the failure before the turn is not kept: the agent has changed the files since, and a stale reason can name a fault that no longer exists.
- **The failure text goes in the message, not in the shell.** `ruff` and `mypy` are on the allowlist already, and the Job log shows the agent used `uv` calls. The text of the failure is the output that the step got, so the agent does not have to find the command. The Job runs `ruff format` after the turn, so the agent does not run it.
- **Fix steps get the turn.** A fix step runs the same static checks. Its message has no list of ticks, as a fix step ticks no task.

## Rejected alternatives

- **Run `ruff check --fix` in the Job.** It would remove an unused import with no turn. But a rule can point at a defect that the model must see, and `_static_failure` says so: the check fixes nothing on purpose. The fix would also change code that the model never read, and it covers `ruff` only. `mypy` has no fix mode.
- **Let the repair turn change any file.** Rejected for the reason above. The check with git is cheap and it is the rule of the tick turn.
- **Two turns when a static failure and an unticked task occur together.** Costs one more conversation turn for a fault that the first turn can fix in one pass. The shared limits would still bound it, but the step would pay for a second ask in every step where the model does both badly. One turn stays.
- **A loop of repair turns.** AGENTS.md rule 2 says stop at a second fix on a fix. The first live failure is one import. A model that cannot fix a lint message in one turn with the text of the message will not do it in three.
- **Report the failure from before the turn when the checks still fail.** The diff of the stop comment shows the checkout after the turn. A reason from before it can name a line that the model has already changed.
- **Add `ruff check` and `mypy` to the verification commands the agent must run.** The agent already may run them. A prompt is a request and not a check. The step is the check.

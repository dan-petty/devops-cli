# Design

## Decisions

**The rule reads the command's tokens, not the step's parser.** `shlex.split` gives the tokens of a `uv run devops ci test <module>` command, and a token whose path is a test module under `tests/` is a module the command runs. A directory token, such as `tests/roadmap/`, is no module. A token with shell syntax around it stays a path and not a module, so the rule never reads a command that the step refuses.

**The group's modules come from its own text.** The `test` task names the module, and `changes`, `creates` and `reads` name the module that the group touches. A behavior group that writes its test in the task text but creates the file through a group path is accepted, as the sample group is.

**A negative search stays accepted.** A behavior group may prove a removed name with `! git grep`, as the rule of #3427 accepts, and no test module exists for it.

**A command with a form problem gets the form problem only.** A second problem for the same command tells the model nothing new, and `form_problems` already refuses a command that the step cannot run.

**The message names the module that the group should run.** The model fixes the command from the problem alone, as it does for every other form problem.

## Rejected alternatives

- **A rule in `check_proposal` rather than `form_problems`.** The fault is the form of a command, which `form_problems` already judges, and the two checks share the command parse.
- **Accept a test directory.** A directory runs every test, and the step then proves more than the group, but it does not prove the group's test: the group's module may not exist yet in a way that the command names.
- **Require the module of the `test` task only.** A group may write its test in a file that a `creates` path names and a task sentence that the `test` text does not name in a code span.

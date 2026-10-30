# Design

## Decisions

- **The job formats, the model does not.** A formatter gives one result for one input. A stop on a format error discards correct work and teaches the model nothing. The job applies the formatter, as an editor does.
- **Format first, then verify.** The format run is the first exit check after the step stages the checkout. The verification commands and the static checks then see the bytes that the commit will hold. A plan whose `Verification:` line is a format check also passes.
- **The changed list is the only input.** `_stage` already lists the paths that the commit would add or change. The formatter gets those that end in `.py`. A file that the agent did not touch is never an argument.
- **Git names the files that changed.** The step stages all, runs the formatter, and lists `git diff --name-only -z` for the changed paths. That list is the files that the formatter changed. The step stages them with `git add`. The step needs no output of ruff, so it needs no parser for it.
- **One muted line.** The line `Formatted: <paths>` goes to the error stream, as the notes of the restore of the ticks do (#2767). A person sees that the job made the change. A run that formats nothing prints nothing.
- **A format error stops the step.** The formatter exits with status 2 on a file it cannot parse, and the step stops with the command and the tail of its output. The step does not retry and does not hide the error. The checkout is reset as for any stop, and the stop comment holds the discarded diff.
- **The format run is a command.** It goes through `_command_failure`, so it has the timeout of the other commands and a timeout stops the step with the same message.
- **`ruff check` stays a check.** A lint rule can point at a real defect, such as an unused name or a bare `except`. The model must see it. The job runs no `--fix`.
- **The prompt tells the model.** One sentence says that the job formats the changed Python files. The prompt is a hint. The job step is the rule.

## Rejected alternatives

- **Keep `ruff format --check` and fix the prompt.** The run for #2656 shows a model that wrote correct code and failed on a wrap. A request does not give a result; AGENTS.md rule 2 asks for a check or a tool.
- **Run `ruff format` on the whole tree.** It would change files that the agent did not touch, and the commit would hold changes that the step did not plan. The issue forbids it.
- **Run `ruff check --fix`.** A fix can hide a lint finding that points at a real defect. The model must see it.
- **Parse the output of `ruff format` for the changed files.** The text of ruff is not a contract. Git gives the list with no parser.
- **Format after the static checks.** `ruff format --check` would be needed again to see a mistake, and the verification commands would run on bytes that the commit does not hold.
- **Ignore a non-zero exit of the formatter.** A syntax error would pass here and stop at `ruff check`. The error would be a second, hidden step. Its status is already the signal.

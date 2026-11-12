# Design

## Decisions

- **The names follow gh.** A `devops gh` command that does the work of a gh command takes gh's noun in the singular. The records show that agents type the gh form from what they know: 0 of 173 failing agent prompts held the singular form (#4833). One rule makes the next name predictable.
- **No alias.** AGENTS.md removes the old path while the project is before 1.0.0. Typer's suggestion names the new group in the usage error, and 121 of 186 agents in the records ran Click's suggestion within 3 calls. When the usage-error record of #4833 shows that plural attempts continue, an alias needs that evidence and the owner's exception.
- **Internal names follow the command.** The sub-app variables (`issue_app`, `run_app`, `label_app`, `secret_app`) and the help keys of `GHCommandHelp` take the new name, so a search for the command finds its code. Test function and test file names stay; they name behavior, not a command line.
- **Capability ids stay.** `gh-issues-close`, `gh-issues-view`, the requirement names and the scenario names are ids, so the deltas change only the text of each requirement and scenario. Archive refuses a MODIFIED block that drops a scenario name.
- **The test reads the command tree through the CLI.** `devops gh <noun> --help` exits 0 for each gh noun of the table, and `devops gh <old> list` exits 2 with the suggestion. A rename back to a plural fails the first test.

## Rejected alternatives

- **Keep the plural and add the singular as a hidden alias.** Rejected: AGENTS.md permits no shim before 1.0.0, and the hidden `rate_limit` alias is the kind of code this change removes.
- **Rename `milestones` to `milestone` too.** Rejected: gh has no `milestone` command, so no gh habit leads agents to the singular; `devops gh milestones` was typed 19 times with 0 singular attempts in the records.
- **A custom "did you mean" handler.** Rejected: Typer's `suggest_commands` (difflib) already prints the suggestion; `uv run devops gh issue view 1` printed `Did you mean 'issues'?` on the base.

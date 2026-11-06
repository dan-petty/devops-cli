# Design

## Decisions

- **Keep the catalog as a typed Python table in `src/devops_cli/roadmap/implement_shell_policy.py`.**: The guard, the prompt and the test already import `SHELL_PROGRAMS` from this module. A second table next to it gives one source for the three readers and a type check at build time.
- **Add `LOCAL_COMMANDS` as its own table, not rows of `SHELL_PROGRAMS`.**: `SHELL_PROGRAMS` names the first word of a command, and the guard, the allowlist of the shell and the log read it. A local command starts with `uv`, so a row in that table would need a second meaning of its name and would change the allowlist.
- **Give each local command the access class of `ShellAccess` and no more.**: `ai repomap`, `ai ast` and `openspec check` are `read`. `docs generate` and `ci test` are `write`, because they write files in the checkout. No command is `network`: the agent has no key in the shell.
- **Fill a third placeholder, `{{local_commands}}`, in the prompt, and render the same table in `docs/ROADMAP_WORKFLOW.md`.**: The prompt file keeps no copy of a table, and a test fails when the document differs from the render, as it does for the two tables of #3072.
- **Test that each cataloged command is a command of the `devops` app with `--help`.**: A renamed command then fails the test and not the agent.
- **Change no counter.**: `uv` is allowed, so a call of a cataloged command is no refusal today. A test pins it.

## Rejected alternatives

- **Adopt open-policy-agent/opa for the catalog.**: It has no table that the prompt and the documents read, no refusal counter, and no scoped-write check. It adds a Rego policy as a second source next to the table.
- **Put the commands in a YAML or TOML file.**: It adds a parser and a second place to keep in step, and the guard is Python code that imports the table.
- **Add `kubectl`, `kube-linter`, `devops review` and `devops ai rag-query`.**: `NOT_IN_RUNNER` leaves the first two out on purpose, and the shell has no key for the last two. #3562 and #3563 hold them.
- **Enforce that a write stays in the checkout.**: The shell check reads the first word only, and `uv run python` writes anywhere the user can. #3565 holds it, with the sandbox of #2695.

# Proposal: #3644

## Why

`devops tf notify-plan` says that it posts a plan comment to a pull request (#3644). It posts nothing: it formats the comment and prints it. The docstring, the help of `--pr`, the MCP tool description in `docs/MCP_TOOLS.md` and the knowledge base row repeat the false claim, so a reader of the MCP schema believes that the read-only tool writes to GitHub. No check finds a command that makes no request and says that it posts.

## What Changes

- The docstring of `tf notify-plan` says that the command formats the plan as a collapsible pull request comment, prints it and sends no request. The MCP tool description and the generated documents follow the docstring.
- The help of `--pr` says that the number goes only into the `pr` field of the structured output, and that the command sends nothing to the pull request.
- The help of `--plan-file` says that the command prints a fixed sample plan when the file is not given or does not exist.
- The unused help text `HELP.tf.notify_plan`, which also claims a post, is deleted.
- A repository invariant fails when the help of a command with the dry-run class `no-external-request`, or the help of one of its options, holds a form of the verb "post".
- The words of a command are observable output, so the change carries a spec delta.

## Capabilities

- `tf-notify-plan` (new): what the command prints and what its words say.
- `command-dry-run-class` (ADDED requirement): a command that makes no external request does not say that it posts.

## Impact

- The command does the same as before. Only its words change.
- The MCP tool `tf_notify_plan` keeps `readOnlyHint: true`, and its description now agrees with it.
- The change fits one pull request.

## Feasibility

- `tf_notify_plan` in `src/devops_cli/commands/tf.py` at origin/main imports no HTTP client and starts no program. It puts `pr_number` in the payload and writes the comment to stdout. A run of `uv run devops tf notify-plan --plan-file plan.txt --json` printed the payload with `"pr": null` and made no request.
- The design of #3235 (`openspec/changes/archive/2026-11-05-3235-read-only-mcp-tools-have-no-write-option/design.md`) records that the command prints the comment and posts nothing, and that this issue fixes the words.
- A probe of every command that `devops` reaches gave 134 of 539 commands with the class `no-external-request`. Of these, only `tf notify-plan` holds a form of "post": in its docstring and in the help of `--pr`. So the new invariant needs no allowlist.
- The same runs showed two more defects: the summary counts come from a fixed text match, and a missing plan file gives the sample plan. They change behavior, so issue #4929 takes them.

## Existing Tool Considered

- Typer and Click render the help, and the test reads the help from the Click command objects. pytest runs the invariant. No open tool compares the words of a command with its dry-run class, so the change writes about 40 lines of test code in `tests/invariants/test_dry_run_class_ratchet.py`. Cost: about 3,000 tokens to write, about 500 tokens for each later fix, and under one hour of elapsed time.
- `devops docs generate --check` already fails when `docs/MCP_TOOLS.md`, `docs/CLI_REFERENCE.md` or `docs/commands/tf.md` differ from the docstring, so no new check reads the catalog.
- Internal code deleted: the unused field `notify_plan` of `TfCommandHelp` in `src/devops_cli/lang/en/help.py`.

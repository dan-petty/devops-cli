# Design

## Context

See proposal.md for motivation and context. The `failover` help attribute on `HELP.ai` in `src/devops_cli/lang/en/help.py` supplies the help text for `devops ai failover`.

## Goals / Non-Goals

**Goals:**
- Update `HELP.ai.failover` in `src/devops_cli/lang/en/help.py` to state that `devops ai failover` records a fallback route in the constellation flag, `devops ai gateway failover` records a failover route for a virtual model, and the gateway's own fallbacks move the traffic.
- Synchronize markdown reference documents with `devops docs generate --sync-readme`.
- Validate the new help output in `tests/test_ai_controller.py`.

**Non-Goals:**
- Modify `devops ai gateway failover` runtime logic or options.
- Alter runtime request dispatching or constellation state persistence.
- Change message strings in `src/devops_cli/lang/en/messages.py`.

## Decisions

### 1. Update HELP.ai.failover directly in `src/devops_cli/lang/en/help.py`

`HELP.ai.failover` is the single source of truth for the help text of `devops ai failover`. Typer binds this string to the command definition in `src/devops_cli/commands/ai.py`.

*Alternative considered:*
- Modify `src/devops_cli/commands/ai_controller.py` docstrings or execution messages: rejected because `HELP.ai.failover` defines the CLI help string that populates the documentation and `--help` output, while command docstrings do not override Typer `help=` keyword arguments.

### 2. Regenerate documentation via repository tooling

`devops docs generate --sync-readme` updates all command references, `README.md`, and `docs/MCP_TOOLS.md` deterministically.

*Alternative considered:*
- Edit generated markdown files manually: rejected because manual edits risk divergence and fail `devops docs check`.

## Risks / Trade-offs

- [Generated docs drift] → Run `uv run devops docs check` to confirm consistency across the repository.

# Design

## Context

`devops --dry-run` resolves delegated commands before execution.
`_descend_subcommand` walks the command tree using Click context creation and Typer command resolution.
Click 8.5.0 mutates the `tokens` list during `curr_cmd.make_context`.
When a command group receives only its own options, all tokens are consumed before `curr_cmd.resolve_command`.
Typer 0.27.2 `_click_resolve_command` reads `args[0]` without checking whether `args` is empty.
This raises `IndexError: list index out of range`.

## Goals

- Prevent `IndexError` when dry-run evaluates a command group given only its own options.
- Support declaring groups such as `ci --check` by forwarding `--dry-run` to the group.
- Support non-declaring groups such as `install-tools --tool kubectl` by printing the generic preview line.
- Place forwarded `--dry-run` after subcommands when group options precede a subcommand.

## Decisions

1. Parse a copy of `tokens` in `_descend_subcommand`:
   `parse_tokens = list(tokens)`
   `ctx = curr_cmd.make_context(curr_name, parse_tokens, parent=parent_ctx, resilient_parsing=False)`
   This preserves the original `tokens` list so length calculations remain accurate.

2. Check `parse_tokens` before calling `curr_cmd.resolve_command`:
   `if not parse_tokens: return None`
   When no tokens remain after option parsing, no subcommand exists.
   The while loop in `_walk_to_leaf` stops, and `curr_cmd` becomes the leaf.

3. Calculate `consumed` using the unmutated `tokens`:
   `consumed = len(tokens) - len(remaining_args)`
   Because `tokens` is not shortened by option parsing, `consumed` includes both the group options and the subcommand.

## Rejected Alternatives

- Patching `typer.core.TyperGroup._click_resolve_command`:
  Rejected because modifying third-party library internals is fragile and unnecessary when caller inputs can be valid.
- Re-parsing the command line with custom regex or argv splitters:
  Rejected because Click already defines option specifications and parsing rules.

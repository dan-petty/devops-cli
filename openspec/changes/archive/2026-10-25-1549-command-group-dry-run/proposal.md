# Proposal

## Why

Issue #1549: `devops --dry-run` on a command group that receives only its own options exits 1 with `IndexError`.
The command `devops --dry-run ci --check` fails because `_descend_subcommand` mutates its `tokens` list.
The Click parser removes parsed options from the list in `make_context`.
When only group options are present, the list becomes empty.
`resolve_command` then accesses `args[0]` on the empty list and crashes with `IndexError`.
The mutation also causes `resolve_proxy_dry_run` to place forwarded `--dry-run` before subcommands.

## What Changes

- `_descend_subcommand` in `src/devops_cli/core/command_resolver.py` parses a copy of `tokens`.
- When the parse leaves no arguments, the group itself is the leaf command.
- If the group declares `--dry-run`, the execution forwards `--dry-run` to the group.
- If the group does not declare `--dry-run`, the command prints the generic delegated preview line and exits 0.
- When group options precede a subcommand, the forwarded `--dry-run` follows the subcommand.
- This change alters no behavior that a consumer observes outside restoring the intended dry-run preview and option forwarding for command groups.
- The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/core/command_resolver.py` (`_descend_subcommand`).
- Tests: `tests/test_main_dry_run.py`.

## Feasibility

- Premise confirmed at commit 69c99cf and current `origin/main` (c5dbafc4).
- `devops --dry-run ci --check` reproduced the crash: `IndexError: list index out of range` in `typer/core.py:1155`.
- `devops --dry-run install-tools --tool kubectl` reproduced the crash: `IndexError: list index out of range` in `typer/core.py:1155`.
- Click 8.5.0 `OptionParser.parse_args` mutates the input `args` list in place.
- Passing a copy `list(tokens)` to `curr_cmd.make_context` prevents the mutation of `tokens`.
- When `parse_tokens` becomes empty after option parsing, returning `None` makes the group the leaf command.
- With unmutated `tokens`, `consumed = len(tokens) - len(remaining_args)` computes `2` for `["--check", "lint"]`.
- The forwarded args for `["--check", "lint"]` become `["--check", "lint", "--dry-run"]`.
- The fix fits in one function in `src/devops_cli/core/command_resolver.py`.

## Existing Tool Considered

Click and Typer provide the underlying CLI framework.
The issue is an in-place list mutation during Click option parsing.
No external library or new dependency is needed.
No internal code is deleted.

# Design

## Decisions

1. **Vendored `typer._click` exception classes and lazy tree loading.**
   `typer.core.TyperGroup` in Typer `0.29.2` inherits from `typer._click.core.Command` (`isinstance(cmd, click.Group)` is `False`, and `click.UsageError is typer._click.exceptions.UsageError` is `False`). Hint inspection imports only `typer._click.exceptions` (`NoSuchOption`, `MissingParameter`, `UsageError`) and loads `usage_hints` lazily inside `_recorded_usage_errors()` so normal commands incur zero extra import time (`startup-imports` invariant).

2. **Separate telemetry classification from display expansion for `NoSuchOption`.**
   - First strip `--help` / `-h` from `NoSuchOption.possibilities`.
   - Next resolve the extra hint line (`resolve_usage_hint`) and call `record_usage_error(error, hinted=hint is not None)` using Click's genuine close matches (never polluted with all options) and exact `hinted` status.
   - Then expand `error.possibilities` on display when empty and the command has at most 6 non-help options, and append `param.help` to `MissingParameter.message` for missing options.
   - Finally, `UsageRecordingGroup.main` prints the one hint line (when present) to `stderr` via `typer._click.echo(..., err=True)` right after `typer.core._main` renders Click's error box and calls `sys.exit(2)`.

3. **Explicit YAML hint table validated at test time.**
   `src/devops_cli/core/usage_hints.yaml` holds declarative `(command_path, typed, reason, hint)` rows loaded through `importlib.resources.files("devops_cli.core")`. `reason` is constrained by Pydantic `Literal["by_design", "other_tool", "other_name"]`. Table invariant tests verify every `devops ...` command cited in a hint resolves via `resolve_devops_argv` and no row repeats Click's own `difflib.get_close_matches` target.

4. **Dynamic `CHECK_ROW_NAMES` and lazy cross-group lookup.**
   - `ci list` and `ci --list` read `CONST_CI_CHECK_ROW_NAMES` from `devops_cli.config.constants` (which `devops_cli.commands.ci` re-exports as `CHECK_ROW_NAMES`) so adding or removing a gate row never leaves stale hints and `core/` imports no command module.
   - Cross-group fallback walks `_root_command()` together with `main._COMMAND_SPECS` via `module_click_command`, respecting `CONST_CLI_ROOT_LEVEL_COMMANDS` (`format`, `lint`) as leaf root commands rather than duplicating the `ci` subtree, checking both group and leaf paths for an exact whole-word segment match or exact split on `-`/`_`, preferring matches within the current command group and deduplicating `gh pr` aliases of `pr`. Ambiguous matches (`> 3` targets) and prefix/partial tokens emit no guess.

## Rejected alternatives

- **Aliases or command forwarding for `roadmap show` or `pr show`.** Rejected by `#4860` (`usage_hints.yaml` rule): aliases dilute canonical command discovery and violate the no-alias invariant in `UsageRecordingGroup` (`src/devops_cli/core/cli.py:201-204`).
- **Monkeypatching `typer.rich_utils.rich_format_error` globally.** Rejected: `typer.core._main` calls `rich_format_error` globally across any Typer instance; overriding `UsageRecordingGroup.main` keeps printing scoped cleanly to the root CLI app and preserves byte-for-byte output when no hint applies (`tests/telemetry/test_usage_errors.py:97`).
- **Hardcoding CI row names in `usage_hints.yaml`.** Rejected: `CONST_CI_CHECK_ROW_NAMES` in `src/devops_cli/config/constants.py` (aliased as `CHECK_ROW_NAMES` in `src/devops_cli/commands/ci.py`) already owns the single registry; duplicating 29 row names in YAML would drift when gate rows change.

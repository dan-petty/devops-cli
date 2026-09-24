# Task 252: Universal Trailing --dry-run Option Propagation Across Subcommands

**Issue**: [#252](https://github.com/dan-petty/devops-cli/issues/252)
**Status**: Done
**Milestone**: `v0.2.20`
**Priority**: `priority/p2-medium`
**Scope**: `scope/cli`

---

## 1. Description & Objectives

When users invoke CLI subcommands with trailing `--dry-run` (such as `devops repos sync --dry-run` or `devops tf apply --dry-run`), Click's top-level callback in `main.py` receives `dry_run=False` (because `--dry-run` was not placed at the root level). It then executes `set_dry_run(dry_run)`, overwriting the global dry-run mode previously detected and activated in `entry.py`. Furthermore, `_lazy_proxy` in `src/devops_cli/core/cli.py` only checks `is_dry_run()`, missing `--dry-run` present in `ctx.args`, and delegates the flag directly to the target module application where Click fails with `Error: No such option: --dry-run`.

### Key Deliverables:
1. **Preserve Global Dry-Run Mode in `src/devops_cli/main.py`**:
   - Ensure the `@app.callback()` in `main.py` only sets `set_dry_run(True)` when `dry_run` is truthy, never overwriting active state set by `entry.py` or environment variables.
2. **Detect & Propagate Trailing `--dry-run` in `src/devops_cli/core/cli.py`**:
   - Update `_lazy_proxy` in `OTelTyper.add_typer` to check `is_dry_run() or "--dry-run" in ctx.args`.
   - When active, strip `--dry-run` from `args`, activate `set_dry_run(True)`, and execute simulated command execution cleanly.
3. **Expose Explicit `--dry-run` on Key Mutating Subcommands**:
   - In `src/devops_cli/commands/repos.py`: Expose `--dry-run` on `sync` / `update` so that directly invoked app instances also support `--dry-run`.
4. **Comprehensive Test Verification**:
   - Expand `tests/test_all_commands_help_dryrun.py` and `tests/test_main_dry_run.py` to assert both leading and trailing `--dry-run` across subcommands.
   - Validate 100% pass across all 10 CI quality gates (`uv run devops ci`).

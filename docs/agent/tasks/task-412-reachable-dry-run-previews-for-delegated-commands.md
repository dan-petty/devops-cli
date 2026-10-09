# Task 412: Reachable `--dry-run` Previews for Delegated Commands

**Issue**: [#412](https://github.com/dan-petty/devops-cli/issues/412)
**Status**: Done
**Milestone**: `v0.2.33`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/cli`, `priority/p1-high`

---

## 1. Description & Objectives

Every command group is registered lazily as a module path, and the lazy proxy short-circuited under dry-run: it printed the generic command line you typed and returned without loading the target module. Detailed previews inside leaf commands were unreachable from the CLI.

This deliverable implements the rule that a command previews only if it declares `--dry-run`:
- Lazy proxy command routing resolves leaf commands and inspects arguments.
- If a command declares `--dry-run` and parsed `dry_run` is false, the proxy forwards arguments with `--dry-run` inserted directly after the command path before any `--` separator or positional arguments.
- If a command does not declare `--dry-run`, the generic preview line is retained without delegating.
- Unknown commands and option syntax errors are caught and surfaced with usage error exit codes.
- Added `--dry-run` option across 24 command modules (55 functions), ensuring previews are reachable without process execution or state mutation.
- Updated `BenchmarkRunner` to avoid writing benchmark reports under dry-run.
- Added structural invariant tests ensuring all callbacks declaring `--dry-run` read their parameter, and callbacks referencing dry-run branches declare `--dry-run`.

#### Key Deliverables:
- [x] Command resolver moved to `src/devops_cli/core/command_resolver.py` and proxy dry-run logic integrated into `src/devops_cli/core/cli.py`.
- [x] Declared `--dry-run` options across 55 command functions across 24 modules with `HELP.options.dry_run`.
- [x] Prevented benchmark report generation in `BenchmarkRunner._evaluate_response` under dry run.
- [x] Structural invariant and acceptance tests in `tests/test_main_dry_run.py` and `tests/test_all_commands_help_dryrun.py`.
- [x] Updated `HELP.main.dry_run`, `docs.compact_cmd`, and `docs/SDLC.md`.
- [x] Documentation synchronized and regenerated via `devops docs generate --sync-readme`.
- [x] All Gated CI validation suite checks passing (`uv run devops ci`).

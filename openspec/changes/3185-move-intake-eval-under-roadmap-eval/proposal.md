# Proposal

## Why

The roadmap group holds evaluations in two places. A person who looks for the evaluation of a job must know which place holds it (#3185). The top-level list carries one evaluation among twelve commands. The change puts the intake duplicate evaluation in the `eval` group, beside the stage, implement and verify evaluations.

## What Changes

- Add `src/devops_cli/commands/roadmap_eval_intake.py` with the intake duplicate evaluation, registered on `eval_app`.
- Decorate `intake` with `@dry_run_class("request-plan")` and delete `"roadmap intake-eval"` from `tests/fixtures/dry_run_gaps.json`.
- Remove the `intake-eval` command from `src/devops_cli/commands/roadmap.py`, with no alias and no shim.
- Import the new module from `src/devops_cli/commands/roadmap_eval.py` so the `eval` group lists it.
- Replace the MCP exclusion entry `("roadmap", "intake-eval")` with `("roadmap", "eval", "intake")` in `tests/ai/mcp/test_mcp.py`.
- Add `tests/commands/test_roadmap_eval_intake.py` for the new path, the removed old name and the unchanged dry run.
- Update `tests/roadmap/test_roadmap_duplicate_eval.py` and `tests/roadmap/test_roadmap_intake.py` to call `("roadmap", "eval", "intake")`.
- Update references in `docs/roadmap/intake.md` and `src/devops_cli/roadmap/intake_duplicate_cases.json`.
- Regenerate the command matrix in `README.md` and CLI references in `docs/CLI_REFERENCE.md` and `docs/commands/roadmap.md`.
- Update spec requirements in `roadmap-intake-duplicates` with the new command path.
- State the execution order against #3186 to prevent merge conflicts.
- The change fits one pull request.

## Order and Dependencies

Issue #3186 splits `roadmap.py` by command kind and touches `intake-eval`. This change moves `intake-eval` first, so #3186 moves only the remaining top-level commands. Issue #3190 shortens command helps and does not touch `intake-eval`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-intake-duplicates`: The intake evaluation runs in the eval group, The moved evaluation keeps its options and its output

## Impact

- Code: `src/devops_cli/commands/roadmap_eval_intake.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/commands/roadmap_eval.py`, `src/devops_cli/roadmap/intake_duplicate_cases.json`
- Documents: `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md`, `docs/roadmap/intake.md`
- Tests: `tests/commands/test_roadmap_eval_intake.py`, `tests/roadmap/test_roadmap_duplicate_eval.py`, `tests/roadmap/test_roadmap_intake.py`, `tests/ai/mcp/test_mcp.py`, `tests/fixtures/dry_run_gaps.json`

## Feasibility

- The search `git grep -n "intake-eval" -- ':!CHANGELOG.md' ':!openspec/changes/archive'` confirms 11 live files citing the old name:
  `README.md:376`, `docs/CLI_REFERENCE.md:6523`, `docs/commands/roadmap.md:33`, `docs/roadmap/intake.md:56`, `openspec/specs/roadmap-intake-duplicates/spec.md:64`, `src/devops_cli/commands/roadmap.py:223`, `src/devops_cli/roadmap/intake_duplicate_cases.json:2`, `tests/ai/mcp/test_mcp.py:599`, `tests/fixtures/dry_run_gaps.json:12`, `tests/roadmap/test_roadmap_duplicate_eval.py:1`, and `tests/roadmap/test_roadmap_intake.py:510`.
- `tests/ai/mcp/test_mcp.py` holds `("roadmap", "eval", "verify")`, confirming that prerequisite #3182 is already merged on main.
- `src/devops_cli/commands/roadmap_eval.py` imports and registers `stage`, `implement`, and `verify` subcommands on `eval_app`.
- The target module `src/devops_cli/commands/roadmap_eval_intake.py` does not exist yet.
- Offline verification commands: `uv run devops ci test tests/commands/test_roadmap_eval_intake.py`, `uv run devops ci test tests/roadmap/test_roadmap_duplicate_eval.py`, `uv run devops ci test tests/ai/mcp/test_mcp.py`, `uv run devops ci docs`, and `! git grep -n "intake-eval" -- ':!CHANGELOG.md' ':!openspec/changes/'`.

## Existing Tool Considered

No open tool covers a rename of this project's own CLI commands.
The change moves one command function, registers it on `eval_app`, and updates all repository references.
The written cost is 4,000 tokens and 1 hour to build, keep, and fix.
The change deletes `intake_eval_cmd` in `src/devops_cli/commands/roadmap.py` and its unused imports.

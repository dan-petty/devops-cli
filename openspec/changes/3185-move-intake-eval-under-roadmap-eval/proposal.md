# Proposal

## Why

The roadmap group holds evaluations in two places, so a person who looks for the evaluation of a job must know which place holds it, and the top-level list carries one evaluation among twelve commands (#3185). The change puts the intake duplicate evaluation in the `eval` group, beside the stage, implement and verify evaluations.

## What Changes

- Add `src/devops_cli/commands/roadmap_eval_intake.py` with the intake duplicate evaluation, registered on `eval_app`.
- Remove the `intake-eval` command from `src/devops_cli/commands/roadmap.py`, with no alias and no shim.
- Import the new module from `src/devops_cli/commands/roadmap_eval.py` so the `eval` group lists it.
- Replace the MCP exclusion entry `("roadmap", "intake-eval")` with `("roadmap", "eval", "intake")` in `tests/ai/mcp/test_mcp.py`.
- Add `tests/commands/test_roadmap_eval_intake.py` for the new path, the removed old name and the unchanged dry run.
- Regenerate the command matrix in `README.md` and the roadmap command reference in `docs/commands/roadmap.md`.
- The change carries a spec delta because the command path that a user types is observable, so `roadmap-intake-duplicates` gains the requirements of the new path.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-intake-duplicates`: The intake evaluation runs in the eval group, The moved evaluation keeps its options and its output, The moved command is excluded from MCP by its new path, The command reference lists the new name

## Impact

- Code: `src/devops_cli/commands/roadmap_eval_intake.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/commands/roadmap_eval.py`
- Documents: `README.md`, `docs/commands/roadmap.md`
- Tests: `tests/commands/test_roadmap_eval_intake.py`, `tests/ai/mcp/test_mcp.py`

## Feasibility

- The issue cites `devops roadmap intake-eval` as a top-level command. `README.md` lists it under the roadmap group: "|  | `devops roadmap intake-eval [OPTIONS]` | Run the intake duplicate evaluation set against the configured analysis model and print the score of each case."
- The issue cites the MCP exclusion list. `tests/ai/mcp/test_mcp.py` holds the entry `("roadmap", "intake-eval"),` in `mcp_command_exclusions`, so the old name exists as a command path of the CLI.
- The issue says #3182 adds `devops roadmap eval verify`. `tests/ai/mcp/test_mcp.py` already holds `("roadmap", "eval", "verify"),`, so that change is in this tree and this item does not wait.
- The issue cites `src/devops_cli/commands/roadmap_eval_stage.py` and `roadmap_eval_implement.py` as the modules to sit next to; both are callers of `eval_app` in the repository map of the staging commit.
- The target module `src/devops_cli/commands/roadmap_eval_intake.py` is no file of the staging commit and no commit deleted or renamed it, so the group creates it.
- First checks against the real system: `uv run devops roadmap eval intake --help` exits 0 and names the intake duplicate evaluation; `uv run devops roadmap intake-eval` exits 2 and reports no such command; `uv run devops ci test tests/commands/test_roadmap_eval_intake.py` passes.

## Existing Tool Considered

No open, maintained tool or library covers a rename of one of this project's own CLI commands. The change is a move of one command function, a registration line and a search for references. The written cost is about 40k tokens and 2 hours to build, nothing to keep and nothing to fix. Keeping a second place for an evaluation costs a reader time on each use.

# Design

## Decisions

- **Put the command in `src/devops_cli/commands/roadmap_eval_intake.py` and register it on `eval_app`.**: It matches the stage, implement, and verify modules and consolidates evaluations under one group.
- **Decorate `intake` with `@dry_run_class("request-plan")` and remove `"roadmap intake-eval"` from `tests/fixtures/dry_run_gaps.json`.**: It satisfies the dry-run class invariant ratchet without leaving stale gap entries.
- **Remove `devops roadmap intake-eval` with no alias and no shim.**: The project is before 1.0.0 and keeps no compatibility shims or redundant command entrypoints.
- **Replace the MCP exclusion entry `("roadmap", "intake-eval")` with `("roadmap", "eval", "intake")` in Group 1.**: It prevents `tests/ai/mcp/test_mcp.py` from failing on unclassified command paths.
- **Update test calls in `tests/roadmap/test_roadmap_duplicate_eval.py` and `test_roadmap_intake.py` in Group 1.**: It ensures all tests pass immediately when the command path changes.
- **Update documentation references in `docs/roadmap/intake.md` and `src/devops_cli/roadmap/intake_duplicate_cases.json`.**: It keeps handbook docs and dataset metadata accurate.
- **Regenerate the command matrix and CLI reference with `uv run devops docs generate --sync-readme`.**: It ensures generated reference documents match the live CLI and pass `devops ci docs`.

## Rejected alternatives

- **Keep the command in `src/devops_cli/commands/roadmap.py` and add an alias under `eval`.**: Pre-1.0.0 policy forbids legacy references, shims, or redundant command routes.
- **Keep `"roadmap intake-eval"` in `tests/fixtures/dry_run_gaps.json`.**: `test_dry_run_class_ratchet.py` fails on stale gap entries that match no existing command.
- **Expose the moved command as an MCP tool.**: Evaluation commands run long-running model calls, and all eval group commands are excluded from MCP.
- **Rewrite historical changelog lines and archived changes.**: `CONTEXT.md` establishes that release changelogs and archived changes are immutable historical records.

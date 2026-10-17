# Task #848: Whole-Tree Import-Cycle and Interface-Layer Invariants

**Issue**: [#848](https://github.com/dan-petty/devops-cli/issues/848)
**Status**: Done
**Feasibility**: Confirmed against Python 3.14 stdlib `ast` and `graphlib.TopologicalSorter` and the live `src/devops_cli` source tree. Walking module-level, non-`TYPE_CHECKING` imports with submodule-first `from pkg import name` resolution yields an acyclic graph over the entire package tree (`TopologicalSorter(graph.edges).prepare()`), and relocating `_load_local_contracts` to `devops_cli.ai.rag.library_store`, release-cut domain helpers to `devops_cli.release.cut`, and `service_job`'s store opener to `devops_cli.roadmap.config.open_roadmap` eliminates all imports of `devops_cli.commands` outside `devops_cli.commands.*` and `devops_cli.main`.

## Summary

Replaced the 4-subsystem Tarjan import-cycle test (`test_no_circular_imports_in_decoupled_subsystems`) with whole-tree import-cycle and interface-layer invariants in `src/devops_cli/core/import_graph.py`, executed inside `test_the_source_tree_keeps_its_structural_invariants()` on its single `_parse_src()` AST pass:

1. **Module-Level Acyclic Import Graph (`src/devops_cli/core/import_graph.py`)**:
   - Uses stdlib `ast` and `graphlib` only; documents that string-based lazy imports are invisible to the static AST import graph.
   - Walks module-level statements outside function bodies and `if TYPE_CHECKING:` blocks, resolving `from pkg import name` to `pkg.name` when `name` is a known submodule in the graph and to `pkg` otherwise.
   - Verifies acyclicity via `graphlib.TopologicalSorter(graph.edges).prepare()`, raising `CycleError` (and formatting violation diagnostics) naming the oriented cycle, `file:line` locations, the rule, and the fix.
2. **Whole-Tree Interface-Layer Invariant**:
   - Enforces at every scope (`_all_imports`) that no module outside `devops_cli.commands.*` and `devops_cli.main` imports `devops_cli.commands`, reporting `file:line`, the rule, and the fix.
   - `devops_cli.core.cli` importing `devops_cli.main` is not a violation because only the `devops_cli.commands` boundary is stated in `ARCHITECTURE.md` and `AGENTS.md`.
   - The vulture step mentioned in `docs/ROADMAP.md:1040` is dropped.
3. **Command-Layer Decoupling**:
   - Moved `load_local_contracts` (`_load_local_contracts`) from `src/devops_cli/commands/ai_ingest.py` into `src/devops_cli/ai/rag/library_store.py` and updated its 3 callers (`src/devops_cli/ai/mcp/server.py`, `src/devops_cli/commands/ai_ingest.py`, and `tests/test_library_vector_tier.py`).
   - Extracted the release-cut domain functions (`cut_release`, `_format_release_title`, `_build_release_pr_command`, `milestone_issues_args`, `milestone_pull_requests_args`, and supporting helpers) into `src/devops_cli/release/cut.py` (re-exported by `src/devops_cli/commands/release.py`), and updated `src/devops_cli/roadmap/close.py`, `src/devops_cli/roadmap/request_plan.py`, and `src/devops_cli/roadmap/run.py` (including calling `open_roadmap` from `devops_cli.roadmap.config` in `service_job`).
4. **Recorded `--durations` Comparison**:
   - Before (`pytest -n 0 --no-cov --durations=0`): `test_the_source_tree_keeps_its_structural_invariants` took `2.43s` and `test_no_circular_imports_in_decoupled_subsystems` took `0.23s` (`2.66s` combined; `0.521s + 0.230s = 0.751s` post-parse analysis).
   - After: `test_the_source_tree_keeps_its_structural_invariants` runs all three whole-tree checks (`measure_tree`, `import_cycle_violations`, and `interface_layer_violations`) on a single `_parse_src()` pass in `0.398s + 0.086s + 0.138s = 0.622s` post-parse analysis (`0.224s` for both import-graph rules vs `0.230s` for the old 4-subsystem Tarjan test alone), with `test_no_circular_imports_in_decoupled_subsystems` and its Tarjan helpers deleted.

## Deliverables

- [x] Create `src/devops_cli/core/import_graph.py` using stdlib `ast` and `graphlib.TopologicalSorter` only, documenting that string-based lazy imports are invisible to the graph.
- [x] Move `load_local_contracts` (`_load_local_contracts`) below the command layer into `src/devops_cli/ai/rag/library_store.py` and update its 3 callers, plus move release-cut domain helpers into `src/devops_cli/release/cut.py`.
- [x] Run `import_cycle_violations` and `interface_layer_violations` inside `test_the_source_tree_keeps_its_structural_invariants()` on its single `_parse_src()` parse, delete `test_no_circular_imports_in_decoupled_subsystems` and its Tarjan helpers, and add the four fixture unit tests.
- [x] Record the `--durations` comparison and the dropped `ROADMAP.md:1040` vulture step in this task file without modifying `pyproject.toml` or `uv.lock`.

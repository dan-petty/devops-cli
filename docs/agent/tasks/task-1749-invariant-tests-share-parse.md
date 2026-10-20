# Task: Invariant Tests Share One Parse of the Source Tree (#1749)

**Issue**: [#1749](https://github.com/dan-petty/devops-cli/issues/1749)
**Scope**: scope/ci
**Feasibility**: Benchmark of repository-wide AST parsing showed that parsing all 577 `src/` modules and 536 `tests/` files once takes ~4.0s total per process. Invariant and architectural tests were each redundantly walking and parsing the entire tree, resulting in test run times between 4.5s and 9.35s and violating #1725's 5s per-test limit. Introducing a session-scoped parsed representation in `tests/support/trees.py` eliminates redundant parses and drops every invariant test call to $\le 1.21$s.

| Test | Before | After |
|---|---|---|
| `test_architectural_invariants.py::test_no_non_submodule_imports_from_ai_and_github_facades` | 9.35s | 1.21s |
| `test_the_source_tree_keeps_its_structural_invariants` | 6.92s | 0.47s |
| `test_public_export_surface.py::test_no_phantom_exports` | 5.89s | 0.71s |
| `test_public_export_surface.py::test_no_duplicate_exports` | 4.79s | 0.01s |
| `test_swallowed_failures_ratchet.py::test_swallowed_failures_stay_under_or_equal_to_ceiling` | 5.46s | 0.96s |
| `test_test_module_independence.py::test_no_test_module_finds_a_path_from_its_own_file_or_imports_a_test_module` | 5.07s | 0.93s |
| `test_no_test_certifies_a_failure_without_checking_it` | 4.91s | 0.54s |
| `test_output.py::test_rich_imports_confined_to_output_submodule` | 4.48s | 0.01s |
| `test_no_direct_data_dir_path_construction_in_src` | 4.35s | 0.70s |
| `test_only_bootstrap_imports_the_support_package_itself` | 4.04s | 0.80s |
| `test_no_module_runs_python_in_process` | 0.50s | 0.56s |

## Description

- [x] Defined `tests/support/trees.py` providing session-scoped fixtures `parsed_source_trees`, `parsed_test_trees`, and `parsed_repo_trees` along with caching helpers `parse_source_trees`, `parse_test_trees`, `parse_repo_trees`, `parse_python_file`, and `parse_count`.
- [x] Implemented `ParsedTreeMap` mapping to allow path resolution on key lookup while preserving mapping invariants for `measure_tree`, `import_cycle_violations`, and `interface_layer_violations`.
- [x] Refactored invariant and architectural tests across `test_architectural_invariants.py`, `test_public_export_surface.py`, `test_swallowed_failures_ratchet.py`, `test_test_module_independence.py`, `test_output.py`, and `test_codebase_hygiene_and_shims.py` to read from the session-scoped parsed representation.
- [x] Added `test_every_source_and_test_file_is_parsed_at_most_once` in `test_architectural_invariants.py` to assert that no file under `src/` and `tests/` is parsed more than once per test process.
- [x] Verified all invariant and architectural assertions and checks remain intact with zero lost coverage.
- [x] Verified `uv run devops ci` passes with 100% status.

# Proposal: #4700

## Why

Closes #4700. Test modules walk `src/` or `tests/` with `rglob("*.py")` and call `ast.parse` on each file. They do not use the per-process cache `parse_python_file` or the session fixture `parsed_source_trees` of `tests/support/trees.py`. So each pytest worker parses the same files again for each test. `test_every_import_of_a_roadmap_module_names_a_module_that_exists` parses 2,127 files and took 10.65 s in CI. The two emit checks of `tests/telemetry/test_telemetry_instruments.py` parse the 795 files of `src/` each time.

## What Changes

- The tests that read `src/` get the trees from `parsed_source_trees`: the gauge, metric and emit checks of `test_telemetry_instruments.py`.
- The other walks of Python files call `parse_python_file`: `test_source_tree.py` (patch, private import and `CliRunner` checks), `test_roadmap_runner_tools.py`, `test_edge_fixtures.py`, `test_github_session.py`, `test_ai_spend_pricing.py`, `test_test_selection.py`, and the fallbacks of `tests/gate/tree_checks/module_independence.py` and `tests/gate/swallowed_failures.py`.
- `test_project_and_tree_fixtures_are_distinct` reads every module of `tests/`. It moves from `tests/invariants/test_hermetic_floor.py` to the `test-tree` row of `devops ci` as `tests/gate/tree_checks/fixture_names.py`, which reads the trees that the row parses once. A probe check of the logic goes with it.
- `test_every_import_of_a_roadmap_module_names_a_module_that_exists` and its helpers are deleted.
- The change alters no behavior that a consumer sees: it changes tests and the code of two `devops ci` rows under `tests/gate/`. It has no spec delta, and `.openspec.yaml` sets `skip_specs: true`.

The change fits one pull request.

## Capabilities

None. The change has no spec delta.

## Impact

- Each pytest worker parses each file of `src/` at most once for these tests. A worker that runs `test_hermetic_floor.py` or `test_source_tree.py` no longer parses all of `tests/`.
- The `test-tree` row runs one more check over the trees that it already holds.
- The roadmap import check goes. mypy refuses a broken import in `src/`, and a broken runtime import in a test fails that test.

## Feasibility

- The audit list of 12 files is `slow-tests/raw_parse_files.txt` of the CI and test audit of 2026-11-11. At `fbe8984d`, an ast-grep census of `ast.parse` calls inside a `for` loop or comprehension over `glob`/`rglob` under `tests/` (not `tests/support/`) gave 10 sites in 7 files. Three more files parse in a helper that a walk calls (`test_github_session.py`, `test_ai_spend_pricing.py`, `test_source_tree.py`), and `test_test_selection.py` and `tests/gate/swallowed_failures.py` collect the walk into a list first. `tests/ai/test_ai_task_loader.py` of the audit list has no parse at `fbe8984d` (#4710 changed it). After the change, the census gives one site: `tests/gate/tree_checks/facades.py:102`, which parses the Python blocks of Markdown files, not Python files.
- mypy: `src/devops_cli/ci/typecheck.py` sets `TYPECHECK_PATHS = ("src",)`, and `mypy --strict` reports a module that does not exist (`import-not-found`) and a name that a module does not have (`attr-defined`). So the gate refuses a broken roadmap import in `src/`.
- Tests: a probe over `tests/` at `fbe8984d` found 1,026 imports of `devops_cli.roadmap`: 904 at module level (collection fails), 3 in a module-level `try`, 104 in a function (the test fails when it runs) and 15 in `if TYPE_CHECKING:` blocks. The 15 do not run, and mypy does not read `tests/`. Each of the 15 modules has `from __future__ import annotations`, so a wrong name there is an annotation only and no test changes its result. The deleted test guarded the module move of #3187, which is complete.
- Memory: `parse_test_trees()` holds 521 MiB of trees for the 1,343 files of `tests/` (`ru_maxrss`, measured). So the check that reads all of `tests/` goes to the `test-tree` row, which holds those trees already, and not to a pytest worker through the cache.

## Existing Tool Considered

The parse cache `tests/support/trees.py` (#1749) and the `test-tree` row of `devops ci` (#2164) cover the need. mypy covers the deleted import check for `src/`. No new tool and no new helper. The change deletes `_roadmap_path`, `_roadmap_import_problems`, `_ROADMAP_DOTTED`, the deleted test, and the second `ast.parse` path of the two gate fallbacks.

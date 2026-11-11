# Design

## Decisions

- **A test that reads all of `src/` takes the session fixture.** `parsed_source_trees` gives the trees of `src/`, parsed once in each worker and shared with the other invariants of that worker. The three checks of `test_telemetry_instruments.py` read it. Each key is under `src/devops_cli/`, so `path.relative_to(SRC)` gives the same labels as before.
- **A walk that reads some files calls `parse_python_file`.** A walk that filters by text first (`mark.live(`, `GitHubClient`, the reference model) or reads one folder (`tests/support/`, `tests/commands/`, `tests/invariants/`, the conftests) parses only those files, once in each process. A helper that took the source text now takes the tree, and its probe test parses its literal source with `ast.parse`.
- **A check over all of `tests/` is a row check.** `test_project_and_tree_fixtures_are_distinct` reads each of the 1,343 modules of `tests/`. docs/TESTING.md puts a check of committed files in a row of `devops ci`, and the `test-tree` row holds the trees of `tests/` already. The check moves to `tests/gate/tree_checks/fixture_names.py` with the same rule: a module under `support/` and a conftest are not read. The probe check `check_a_second_project_or_tree_fixture_is_named_with_its_paths` gives it in-memory trees.
- **The gate fallbacks read the cache.** With no trees, `module_independence._violations` reads `parse_test_trees(root)`, and `collect_ast_unread_check_false` calls `parse_python_file`. So each module has one parse path.
- **The roadmap import check is deleted.** It guarded the move of #3187. mypy refuses a broken import in `src/`. A broken import at module level in a test fails collection, and one in a function fails that test. The 15 imports in `if TYPE_CHECKING:` blocks of tests are annotations under `from __future__ import annotations`, and no test result depends on them.

## Rejected alternatives

- **Keep the roadmap import check and read `parse_repo_trees()`.** The cache would hold the trees of `src/` and `tests/` (358 MiB and 521 MiB, measured with `ru_maxrss`) in the worker, and the first test in that worker would still parse 2,142 files, because no other pytest test reads all of `tests/`. The check would cost about the same time and more memory.
- **Route `test_project_and_tree_fixtures_are_distinct` through `parse_python_file` in pytest.** It is the only pytest test that reads all of `tests/`, so the cache gives it no shared parse. It would keep the parse time and hold 521 MiB in the worker.
- **A text filter before the parse of the fixture check.** A filter on `def project(` would make the parse small, but it would add a second, text-based rule beside the tree rule. The row holds the trees already.
- **An ast-grep rule that refuses `ast.parse` of a file read under `tests/`.** It finds a direct call only. Three of the files parse in a helper that a walk calls, and 7 more files parse one fixed file, which is no repeated work. The rule would refuse correct code or miss the helper form.

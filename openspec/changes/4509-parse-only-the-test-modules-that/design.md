# Design

## Decisions

- `counts_in` tests the text for `REGISTRY_COUNTS` after it reads the file and before `ast.parse`. The parse of a module that holds the name does not change, so a name in a comment, a string or a function body still gives no entry.
- `registry_table` makes the relative path only for a module that gives an entry. For the 1,340 modules, `Path.relative_to` took 0.023 s, about one seventh of the call after the change.
- The function keeps no state between calls. The Service runs for days, and a table with no cache cannot go stale.
- The test sees the calls of `ast.parse` through `sys.monitoring` (PEP 669). It takes a free tool id, records the first argument of each `CALL` event whose callable is `ast.parse`, and frees the id at the end. It does not replace `ast.parse` or a devops-cli name, as docs/TESTING.md (Doubles) asks.
- The stage gate tests pass `registry=()`. An empty table gives no registry problem. The tests of the registry gate give a table: `test_roadmap_stage_split_gates.py` builds it from its clone, one test of `test_roadmap_stage_plan.py` gives its entries, and the test of a new roadmap limit builds the table of the checkout, because it checks the real declaration of `tests/roadmap/test_roadmap_limit_classes.py`.

## Rejected alternatives

- A cache in `registry_table`, keyed on the path, `st_mtime_ns` and `st_size` of each module: 0.037 s on a warm call against 0.092 s for the substring test (measured in the CI audit). The gain is small, and a cache adds state to the long-lived Service.
- A `conftest.py` in `tests/roadmap/stage/` that replaces `registry_table` in `stage_change` with a function that raises: docs/TESTING.md (Doubles) says that no test patches a devops-cli function. #4695 makes `registry` a required argument of `check_gates` and `check_proposal`, and then the interpreter refuses a call with no table.
- A test that counts the calls of `ast.parse` in `check_proposal` with `registry=()`: the call gives no table build before or after this change, so the test passes on the base and proves nothing. Other gates also parse Python text, so a count of zero is not true for each plan.
- A regular expression or a search tool in place of `ast`: the gate needs the line and the literal values of each entry, and only the parse gives them. The substring test only filters.
- A module can spell the name with characters that NFKC folds to `REGISTRY_COUNTS` (PEP 3131), and the substring test does not see it. No module of the tree does this, and a test module has no reason to do it, so the change accepts this limit.

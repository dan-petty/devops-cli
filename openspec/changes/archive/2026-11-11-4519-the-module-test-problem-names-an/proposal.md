# Proposal: The module-test problem names the nearest test

## Why
The `paths` gate of the stage job refuses a behavior group that changes a module and names none of its tests. The problem names the first test of the record in path order. For `src/devops_cli/lang/en/messages.py` the record holds about 56 tests that import `devops_cli.lang`, and the problem names `tests/ai/mcp/test_ai_benchmark_mcp_tool.py`. The model then reads a test that has no relation to its change, or it repeats the refusal. Closes #4519.

## What Changes
- `record_module_tests` lists the tests of each module nearest first: the mirror test, a test that imports the module by its own name, a test in the mirror folder, then the rest. Each class keeps path order.
- A test that only another changed module imports comes after every test of the module itself.
- `_unnamed_module_test` keeps `tests[0]`, so the problem names the nearest test. The sentence does not change.
- A module at the top of the package has no mirror folder and no mirror test.

## Capabilities
- Modified: `roadmap-stage`.

## Impact
The refusal sentence of the stage job names a test that the model can use. No test leaves the record. No other caller changes: `stage.py` and `plan_recheck.py` pass the record on.

## Feasibility
Checked on `origin/main` (0.112.1). `record_module_tests` in `src/devops_cli/roadmap/stage/stage_paths.py` returns `tuple(sorted(tests))`, and `_unnamed_module_test` returns `tests[0]`. `tests/lang/` holds no mirror of `en/messages.py`, so the 56 importers fall to the direct-import rule. `_importing_tests` already reads the import edges of each test with `build_import_graph`, so it can tell a direct import from a package import. The premise holds.

## Existing Tool Considered
The issue records that no alternatives check has run. No open tool holds the import graph of this project. The change reuses `build_import_graph` and adds one small sort key. Cost to build: about 15,000 tokens and 1 hour; to keep: about 1,000 tokens a year.

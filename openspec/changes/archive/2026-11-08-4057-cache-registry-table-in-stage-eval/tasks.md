# Tasks

## 1. Add the tests that pin the single registry read of the replay

Reads: `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `src/devops_cli/roadmap/stage/stage_registry.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`. Changes: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.

- [x] 1.1 Add two tests to `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`. `test_the_replay_reads_the_registry_table_once` uses `monkeypatch.setattr` to replace `registry_table` on the replay module with a counter that returns an empty table, replays the first two cases of the `cases` fixture through `replay_all`, and asserts that the counter reads one. `test_the_plan_under_test_holds_the_registry_of_its_case` builds `PlanUnderTest.of_case(case, registry=table)` with a one-entry `RegistryCount` and asserts that `plan.registry` is that table. Change no source file
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` passes

## Criteria

- Group 1: `uv run pytest tests/roadmap/stage/test_roadmap_stage_eval_gates.py -k registry` - `registry_table` is called at most once during replay of multiple cases.
- Pending person: `uv run devops roadmap eval stage --replay` finishes in less than 60 seconds., The rule `test-elapsed-upper-bound` in `.ast-grep/rules/` fails a test that bounds elapsed time from above, so a person runs the command on the real system and reads its elapsed time against the 60-second bound.

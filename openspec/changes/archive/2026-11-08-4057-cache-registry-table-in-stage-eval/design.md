# Design

## Decisions

- **Add two regression tests and change no source file.**: Commit 84761630 already threads the table: `src/devops_cli/roadmap/stage/stage_eval_gates.py:177:registry=plan.registry,` gives it to `check_proposal`, and `src/devops_cli/roadmap/stage/stage_eval_gates.py:419:table = registry if registry is not None else registry_table(Path.cwd())` reads it once per replay.
- **Leave `registry_table` uncached, with no `functools.lru_cache`.**: A process-wide cache is keyed only by `root`, so it serves a stale table after the tests tree changes at the same path, and `src/devops_cli/roadmap/stage/stage.py:1024:registry = registry_table(self._source)` reads the table on each round of one process; one read per replay already removes the per-case walk.
- **Put the two new tests in the existing module `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.**: That module holds the replay tests and the module-scoped `cases` fixture, so the new tests reuse them, and the counting test is named with `registry` so the command of the first criterion selects it.
- **Give the 60-second criterion to a person.**: The rule `test-elapsed-upper-bound` in `.ast-grep/rules/` fails a test that bounds elapsed time from above, so no offline test can assert the duration.

## Rejected alternatives

- **Add `functools.lru_cache` to `registry_table`, as the Expected section of the issue asks.**: The cache lives for the whole process and is keyed only by `root`, so a later round on the same path reads a stale table; `src/devops_cli/roadmap/stage/stage.py:1024:registry = registry_table(self._source)` calls it again on each round, and one read in `replay_all` already gives one walk per replay.
- **Add the `registry` parameter to `PlanUnderTest.of_case`, `replay_case` and `replay_all` again.**: Those lines exist at the staged commit, as `src/devops_cli/roadmap/stage/stage_eval_gates.py:81:registry: Sequence[RegistryCount] | None = None` and `src/devops_cli/roadmap/stage/stage_eval_gates.py:419:table = registry if registry is not None else registry_table(Path.cwd())` show, so a second addition duplicates code.
- **Assert in the test module that the whole replay takes less than 60 seconds.**: `.ast-grep/rules/test-elapsed-upper-bound.yml` fails an assert that bounds elapsed wall-clock time from above, and the `constructs` row of `uv run devops ci` runs that rule.
- **Read the table inside `PlanUnderTest.of_case`.**: Each of the 47 cases would then walk the tests tree again, which is the 53,862 parses that the issue reports; `replay_all` reads the table once instead.

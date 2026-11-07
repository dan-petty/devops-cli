# Proposal

## Why

Issue #4057 reports that `devops roadmap eval stage --replay` took 615 seconds, because each of the 47 golden cases walked every test module and parsed it to build the registry table. The single read is in the staged tree from commit 84761630, and no test pins it, so a later change can restore the per-case walk with nothing to catch it.

## What Changes

- Add `test_the_replay_reads_the_registry_table_once` to `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`: it replaces `registry_table` in the replay module with a counter, replays two recorded cases and asserts that the counter reads one; its name holds `registry`, so the `-k registry` command of the first criterion selects it.
- Add `test_the_plan_under_test_holds_the_registry_of_its_case` to the same module: it asserts that `PlanUnderTest.of_case` stores the one-entry table that it is given.
- Leave `registry_table` uncached: one read per replay already removes the per-case walk, and a process-wide cache keyed only by `root` can serve a stale table after the tests tree changes at that path.
- The change touches only `tests/`, so it has no spec delta: it changes no behavior that a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`

## Feasibility

- The probe of the cited module answers: "The path `stage_eval_gates.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_eval_gates.py`. No commit in the history deleted or renamed it." So the module that the issue cites is `src/devops_cli/roadmap/stage/stage_eval_gates.py` at the staging commit.
- The probe of the rule file answers: "The path `AGENTS.md` is a file of the staging commit." Its rule 5 makes a check that averages more than 5 minutes a P0 bug, which is the reason the issue gives.
- `functools.lru_cache` is a function of the Python standard library that the issue asks to apply, not a repository path.
- `read_file` of `src/devops_cli/roadmap/stage/stage_eval_gates.py` shows the threading that the issue asks for is in the staged tree: `src/devops_cli/roadmap/stage/stage_eval_gates.py:81:registry: Sequence[RegistryCount] | None = None`, `src/devops_cli/roadmap/stage/stage_eval_gates.py:88:registry: Sequence[RegistryCount] | None = None,`, `src/devops_cli/roadmap/stage/stage_eval_gates.py:114:registry=registry,`, `src/devops_cli/roadmap/stage/stage_eval_gates.py:177:registry=plan.registry,`, `src/devops_cli/roadmap/stage/stage_eval_gates.py:308:problems = run_gates(PlanUnderTest.of_case(case, registry=registry))` and `src/devops_cli/roadmap/stage/stage_eval_gates.py:419:table = registry if registry is not None else registry_table(Path.cwd())`.
- `git_show` of 84761630 shows that commit added the field, the parameter, the gate call and the single read in `replay_all`, so a second addition would duplicate code.
- `read_file` of `src/devops_cli/commands/roadmap_eval_stage.py:34:report = replay_all(select_cases(load_cases(cases_dir), names, limit))` shows that `--replay` calls `replay_all` with no table, so one read in `replay_all` serves every case of the run.
- The issue says `_path_gate` calls `check_proposal` with `registry=None`; the staged line is `registry=plan.registry,`, so that part of the issue is out of date and the plan writes no code for it.
- `functools.lru_cache` on `registry_table` is not added: `src/devops_cli/roadmap/stage/stage.py:1024:registry = registry_table(self._source)` reads the table on each round of the long-lived Service, and a cache keyed only by `root` would serve a stale table after the tests tree changes at that path.
- `registry_table` needs a checkout of the repository: it walks the tests tree with `rglob` and parses each module, as `src/devops_cli/roadmap/stage/stage_registry.py:95:for file_path in sorted(search_dir.rglob("*.py")):` shows.
- `replay_all` needs a checkout of the repository when the caller gives no table, since it then reads one from `Path.cwd()` (`src/devops_cli/roadmap/stage/stage_eval_gates.py:419:table = registry if registry is not None else registry_table(Path.cwd())`).
- `load_cases` needs a checkout of the repository: the module fixture passes `REPO_ROOT / CASES_DIRECTORY`, the folder of the recorded cases under the checkout.
- `replay_case` and `PlanUnderTest.of_case` need no checkout, no client and no network when the caller gives them a table, because a case carries its own recorded tree.
- `check_proposal` needs a checkout of the repository when the plan holds no table, since `check_gates` then walks `Path.cwd()` (`src/devops_cli/roadmap/stage/stage_change.py:1197:registry if registry is not None else registry_table(Path.cwd()),`).
- The first check against the real system is `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, which runs the two new tests.
- The second check is `uv run devops roadmap eval stage --replay`, whose elapsed time a person reads against the 60-second bound.
- The module `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` holds no test whose name holds `registry`, so the `-k registry` command of the first criterion selects no test today; the new test name holds `registry`.
- The rule `.ast-grep/rules/test-elapsed-upper-bound.yml:1:id: test-elapsed-upper-bound` fails an assert in `tests/` that bounds elapsed time from above, so no offline test asserts the 60-second bound.

## Existing Tool Considered

The pytest `monkeypatch` fixture counts the calls of `registry_table` offline, and the standard library `functools.lru_cache` covers a process-wide cache that this change declines. No new dependency is added and no library is built.

## Dependencies

None.

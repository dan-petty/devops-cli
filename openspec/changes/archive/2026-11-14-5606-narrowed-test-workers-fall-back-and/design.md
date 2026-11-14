# Design

## Decisions

- **Give the collection `--snapshot-warn-unused`, through one module constant `_SNAPSHOT_WARN_UNUSED` that the shard command also uses.**: A collection runs no test, so syrupy finds each snapshot of a selected module unused and exits 1. The shard rows already give the same option for the same reason (a shard leaves the snapshots of other shards unused), and one constant keeps the two the same.
- **Model syrupy in the fake answer, not only the argv.**: `_answer_collection_with_unused_snapshots` exits 1 when the collection argv lacks the option and 0 when it has it, with the 422 test ids in both outputs, as the real run printed. So the case fails when the option goes away, and it shows the result that the person sees: the workers and no warning.
- **Bound the workers with `PYTEST_XDIST_AUTO_NUM_WORKERS` in `_worker_cap`, as `min(DEFAULT_CI_TEST_NARROWED_WORKERS, value)`.**: A runner pod sets the variable to its CPU limit, because xdist counts the CPUs of the node (#2806). xdist reads it only for `-n auto` and `-n logical`, and the narrowed run gives an explicit `-n`. The function ignores a value that `int()` refuses, as `pytest_xdist_auto_num_workers` of xdist does.
- **Read the name of the variable from `WORKERS_VARIABLE` of `src/devops_cli/roadmap/implement/implement_size.py`, imported in the function body.**: The Service sets the variable from that name, and the gate check `tests/gate/k8s_checks/job_admission_policy.py` imports it from there. The function body already imports `collected_items` from the roadmap package in the same way, so the startup imports of `devops ci` do not change.
- **Run serially with no collection when the cap is 1 or less.**: `-n 1` starts one xdist worker, which costs a start-up and runs no test in parallel, and the collection cannot change a serial answer. A value of 0 is the serial run that xdist gives for 0.
- **Run on the cap with no collection when more than `DEFAULT_CI_TEST_SERIAL_MAX_TESTS` target modules have no `-k` filter.**: Each target module collects one test at least, so the count is above the limit and the collection cannot change the answer. A change to a shared source module selects many test modules, and its collection is the largest: the whole suite took 55 s to collect. A `-k` filter can leave fewer tests, so a selection with a filter still collects.
- **Keep the collection for all other selections, and keep the limit of 50 tests.**: The issue asks to bound the collection, not to remove it. Up to 50 target modules can collect more than 50 tests, as the 7 modules of #4472 collect 422, and only the collection finds that.
- **Set `DEFAULT_CI_TEST_COLLECTION_TIMEOUT_SECONDS` to 120 s.**: The start-up of pytest is most of the time of a collection: pytest reported 0.31 s to 1.03 s of collection for the 7 modules of #4472, in sessions of 7.1 s and 21.6 s. Measured wall time on 16 CPUs: 6.2 s to 7.9 s for 1 module, 7.1 s for the 7 modules at a load of 6, 21.6 s for the 7 modules with a cold cache, 55 s for the whole suite, and 23 s to 47 s for a narrowed selection at a high load (the vet of #5606). 120 s is above 2.5 times the slowest narrowed sample and far below the 1800 s timeout of the run, so the inner limit fires first and the run continues on the file count.
- **Print the warning of a failed collection with `safe=True`.**: The warning holds the command, with the targets and the `-k` value. Without `safe=True`, Rich reads `[/x]` as a closing tag and raises `MarkupError`, and reads `[bold]` as a style and hides it.
- **Put the 12-module boundary back as a parametrized case of the fallback, with 12 and 13 modules.**: The file count decides only when the collection gives no count, so the boundary of `DEFAULT_CI_TEST_SERIAL_MAX_FILES` is a property of the fallback. The case that #5547 deleted asserted the same 12 and 13.
- **Add a `--repeat` case to the cases that make no collection.**: `_run_shuffled_repeats` returns before the worker choice, and the case keeps that order.
- **Remove `PYTEST_XDIST_AUTO_NUM_WORKERS` for each test of `tests/commands/test_test_selection.py` with the fixture `no_worker_bound`, which `pytestmark` names.**: A runner Job sets the variable, and the tests of this module run in that Job when a change selects them. Without the fixture, a Job with 1 CPU gives `-n 0` and no collection, and the cases that expect the cap or a collection fail. The fixture is local to the module, so the hermetic floor and the other tests do not change.
- **Read `DEFAULT_CI_TEST_COLLECTION_TIMEOUT_SECONDS` through the `defaults` module in the body of the timeout case.**: `devops ci fail-to-pass` replays the changed tests on the base. A module-level import of the new constant stops the collection of the module on the base, and no case runs there.

## Measurements

The narrowed run of one 52-test module, `uv run devops ci test tests/roadmap/test_roadmap_claim.py`, end to end, on this host (16 CPUs, load 0.4 to 2.7, two runs each):

| Run | Before (`origin/main` b15faabb7) | After (this change) |
| --- | --- | --- |
| 1 CPU (`taskset -c 3`), `PYTEST_XDIST_AUTO_NUM_WORKERS=1` | 37.2 s, 37.7 s: collection, then `-n 4` | 8.6 s, 8.4 s: `-n 0`, no collection |
| 16 CPUs, variable not set | 20.6 s, 20.9 s: collection, then `-n 4` | 22.3 s, 21.9 s: collection, then `-n 4` |

For reference, `-n 0` of the same module took 7.9 s and 8.4 s on 1 CPU, and 8.4 s and 8.8 s on 16 CPUs. The 52 tests ran in 0.3 s serially, and in 6.9 s to 7.7 s on 4 workers, so a pytest start-up of 6 s to 8 s is most of each session.

The selection of #4472, `uv run devops ci test` with its 7 modules, ran on this change with no collection warning and exited 0: `4 workers [422 items]`, `422 passed in 62.53s`, 78 s end to end, at a load of 6. Its collection alone, `uv run pytest -n 0 --collect-only -q --snapshot-warn-unused` with the 7 modules, exited 0 with `422 tests collected` in 7.1 s.

The scoped run of this change, `uv run devops ci test` with the 3 changed source files and the changed test module, selected 166 test modules: it made no collection and ran `4 workers [5834 items]`, `5834 passed in 175.16s`, 185 s end to end.

## Rejected alternatives

- **Accept exit 1 of the collection when its output holds test ids.**: Exit 1 is pytest's `TESTS_FAILED`, which any plugin can set through the session status, and syrupy is only one of them. The code does not name the cause, so the command cannot tell a syrupy exit from a real failure. `--snapshot-warn-unused` removes the cause.
- **Run the collection with `-p no:syrupy`.**: The run itself loads syrupy. The design of #4472 makes the collection the run's own command, so that the count follows the run, and a second form of the command can drift from it.
- **Give the run `-n auto` or `-n logical` and let xdist read the variable.**: The root conftest wraps `pytest_xdist_auto_num_workers` so that such a run waits for a gate slot (#4525), and with no variable it starts up to the CPUs of one gate slot, 16 on this host, against the cap of 4 that #1669 measured.
- **Use `-n 1` for a cap of 1.**: It starts one worker process for no parallel gain. `-n 0` runs the tests in the pytest process.
- **Skip the collection for more than `DEFAULT_CI_TEST_SERIAL_MAX_FILES` (12) target modules.**: That changes the rule of #4472 instead of bounding its cost: 13 to 50 modules can collect 50 tests or fewer, and the collected count then runs them serially. Only more than 50 modules prove more than 50 tests.
- **Remove `PYTEST_XDIST_AUTO_NUM_WORKERS` in the hermetic floor of `tests/conftest.py`.**: The floor runs for each test of the suite, and a test that starts a real pytest child would lose the bound of its pod. Only the tests of this module read the variable through the command.
- **Keep `DEFAULT_SUBPROCESS_TIMEOUT_SECONDS` for the collection.**: It is 1800 s, the same limit as the run, so a collection that hangs uses the time of the run and the outer limit fires first.
- **Lower the limit of 50 tests, or size the workers by the time of the tests.**: The 52-test module above ran in 8 s serially and in 22 s with the collection and 4 workers, so a count of tests is a poor sign of the work. That is a change of the rule of #4472 and needs a source of test times, which the project does not keep; the issue does not ask for it, and #5612 tracks it.

## Unchanged references

- `src/devops_cli/roadmap/implement/implement_size.py` (definition): `WORKERS_VARIABLE` keeps its home, and the command imports it from there.
- `src/devops_cli/roadmap/implement/implement_step.py` (other collection): Its test-form check runs `uv run pytest --collect-only -q -- <path>` with no `-n 0`, so `addopts` gives `-n logical`. syrupy then gets no report from the xdist workers and skips the check of unused snapshots: `tests/output/test_output.py` printed `1 snapshot unused.` and exited 0. So that check does not have defect 1, and this change does not touch it.
- `openspec/changes/archive/2026-11-13-4472-a-narrowed-ci-test-runs-many/design.md` (archived design): It records the decisions of #4472 as they were, and this design records what changed.

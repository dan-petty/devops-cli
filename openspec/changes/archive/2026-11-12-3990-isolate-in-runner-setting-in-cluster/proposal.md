# Proposal: #3990

## Why

Issue #3990: the pod of a runner Job sets `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER=true`, and the implement job runs the test suite in that pod. A setting variable wins over the config file, and the floor of the suite does not remove this variable. So in the pod, `roadmap.implement.in_runner` is true in each test, also in a test that sets it false in its config. The tests of the outside-runner path then take the in-runner path and fail. In an implement run, these false failures start repair rounds that spend the token budget and stop the item.

## What Changes

- `isolate_devops_cli_config` in `tests/conftest.py`, the autouse fixture that gives each test its own config, removes `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER` for the test. With the `DEVOPS_CLI_CONFIG` and `DEVOPS_CLI_DATA_DIR` that the floor already sets, the floor now isolates each setting variable that the runner manifest sets. A test that needs the in-runner path sets `roadmap.implement.in_runner` in its config, as it does now.
- The test `test_the_job_runs_no_step_unless_the_setting_says_it_is_in_a_runner` in `tests/roadmap/implement/test_roadmap_implement_records.py` no longer removes the variable itself.
- A new test in `tests/invariants/test_hermetic_floor.py` runs the floor in pytester with the variable set in the outer environment, and the inner test sees no such variable and a false setting.
- `docs/TESTING.md` names the removal in the hermetic floor.
- The issue proposes the removal in the `cluster_jobs` fixture. The leak also fails 3 tests that do not use that fixture, so the change removes the variable in the floor (see `design.md`).
- The change alters no behavior a consumer observes. It changes only the test floor, its tests and a document. So it has no spec delta and sets `skip_specs: true`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: the suite gives the same results in the pod of a runner Job and on a workstation.
- Files: `tests/conftest.py`, `tests/invariants/test_hermetic_floor.py`, `tests/roadmap/implement/test_roadmap_implement_records.py`, `docs/TESTING.md`.
- No path under `src/` changes.

## Feasibility

- The premise holds at `origin/main` (`f55a20b99`). `setting_sources` in `src/devops_cli/config/settings.py` puts `SettingVariables` before the config file, so the variable wins over the config of a test. `k8s/devops/cronjob-runner.yaml` sets 3 setting variables (`grep -c "name: DEVOPS_CLI_" k8s/devops/cronjob-runner.yaml` prints 3): `DEVOPS_CLI_CONFIG` and `DEVOPS_CLI_DATA_DIR`, which the floor already sets for each test, and `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER`, which no fixture of the floor removes.
- `DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER=true uv run devops ci test tests/roadmap/implement/test_roadmap_implement_outside.py` gives 23 failed and 8 passed, as the issue says.
- The same variable also fails 3 tests that do not use `cluster_jobs`: `test_confirm_outside_a_runner_exits_1_and_runs_nothing` (`test_roadmap_implement_command.py`), and `test_the_job_runs_no_step_unless_it_is_in_a_runner` and `test_a_job_outside_a_runner_does_not_touch_its_process` (`test_roadmap_implement_job.py`). Each sets `in_runner` false in its config, and the variable wins.
- `test_roadmap_implement_records.py` holds the one test that removes the variable itself (`git grep -n "delenv(\"DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER\"" -- tests` prints 1 line).
- pytest 9.1.1 is in the lock. `monkeypatch.delenv(name, raising=False)` removes the variable for one test and puts it back at teardown.

## Existing Tool Considered

- pytest's built-in `monkeypatch` fixture covers the need: `monkeypatch.delenv(name, raising=False)`. The floor fixture already uses `monkeypatch.setenv` for the other variables. No new dependency and no new helper.
- The change deletes the `monkeypatch.delenv` call and the `monkeypatch` parameter of `test_the_job_runs_no_step_unless_the_setting_says_it_is_in_a_runner`.

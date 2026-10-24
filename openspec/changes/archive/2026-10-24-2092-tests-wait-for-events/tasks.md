# Tasks

## 1. A second Ctrl-C cannot skip the SIGKILL

- [x] 1.1 Write `test_a_second_ctrl_c_just_after_the_stop_sends_its_sigint_cannot_skip_the_sigkill` in `tests/test_ci.py`, which raises each Ctrl-C at the two points that a loaded host made possible, and make the handler tests cover SIGINT. Verify that the new test fails on the base with `uv run devops ci test tests/test_ci.py -k second_ctrl_c_just_after`
- [x] 1.2 Add SIGINT to `CONST_CI_RUN_STOP_SIGNAL_NAMES` in `src/devops_cli/config/constants.py`, so the run of `devops ci test` takes over Ctrl-C, and verify with `uv run devops ci test tests/test_ci.py tests/test_process.py`
- [x] 1.3 Correct the docstrings in `src/devops_cli/commands/ci.py` and `src/devops_cli/core/process.py` and the stop of `devops ci test` in `docs/TESTING.md`, run `uv run devops docs generate --sync-readme`, and verify with `uv run devops docs check`

## 2. A stop signal wakes the run wherever it lands

- [x] 2.1 Write `test_each_stop_signal_cancels_the_run_through_the_event_loop` in `tests/test_ci.py`, which gives `_cancelled_by_stop_signals` a loop that records its signal handlers, and starts no process and sends no signal. Verify that it fails with the `signal.signal` handlers with `uv run devops ci test tests/test_ci.py -k each_stop_signal_cancels`
- [x] 2.2 Make `_cancelled_by_stop_signals` in `src/devops_cli/commands/ci.py` set the handlers with `loop.add_signal_handler`, and verify with `uv run devops ci test tests/test_ci.py tests/test_process.py`
- [x] 2.3 Write the handlers of the run in `docs/TESTING.md`, and verify with `uv run devops docs check`

## 3. The signal tests wait for the start of devops with no bound of their own

- [x] 3.1 Write the tests of `wait_while_running` in `tests/test_support_waits.py`: an event later than the handoff bound while the process runs, and an exit with no event. Verify with `uv run devops ci test tests/test_support_waits.py`
- [x] 3.2 Add `wait_while_running` to `tests/support/waits.py`, and make the end-to-end signal tests in `tests/test_ci.py` wait through it for the fake `uv`'s pids and with `Popen.wait()` for the exit of `devops`. Verify with `uv run devops ci test tests/test_support_waits.py tests/test_ci.py`
- [x] 3.3 Write the rule for a wait on a process that the test started in `tests/support/waits.py` and `docs/TESTING.md`, and verify with `uv run devops docs check`

## 4. The UI test holds its fetch until it releases it

- [x] 4.1 Make `test_a_slow_subsystem_does_not_freeze_the_interface` in `tests/test_ui_reactive.py` hold the k8s fetch with no bound, release it in a `finally` inside the app's context, and wait for the worker with `THREAD_HANDOFF_BOUND_SECONDS`. Verify with `uv run devops ci test tests/test_ui_reactive.py`

## 5. Every run loads Hypothesis's ci profile

- [x] 5.1 Write `test_the_properties_run_under_the_ci_profile_so_a_loaded_host_cannot_fail_them` in `tests/test_sandbox_policy_properties.py`, and verify that it fails on the base with `uv run devops ci test tests/test_sandbox_policy_properties.py`
- [x] 5.2 Add `--hypothesis-profile=ci` to `addopts` in `pyproject.toml` and to the pin of `addopts` in `tests/test_test_selection.py`, and verify with `uv run devops ci test tests/test_sandbox_policy_properties.py tests/test_test_selection.py tests/security/test_sarif_fuzzing.py tests/review/test_review_json_fuzzing.py tests/argo/test_gitops_fuzzing.py tests/core/test_cleanup_fuzzing.py tests/ci/test_cache_fuzzing.py`
- [x] 5.3 Write the profile in the property test rules of `docs/TESTING.md`, and verify with `uv run devops docs check`

## 6. The clock contract measures from the opening of the window

- [x] 6.1 Make the ratelimit case of `tests/core/test_clock_contract.py` measure from a seam reading taken just before the window opens, assert the lower bound in the real case and the one wait in the fake case, and verify with `uv run devops ci test tests/core/test_clock_contract.py`

## 7. Checks

- [x] 7.1 Run each test of #2092 and #2069 50 times under CPU load with `uv run devops ci test <files> -k <tests> --repeat 50`
- [x] 7.2 Run `uv run devops ci test tests/test_swallowed_failures_ratchet.py tests/test_architectural_invariants.py` and `uv run devops ci --only lint,format,typecheck,docs,openspec`

## Workflow follow-up

- The other waits in `tests/` that keep a deadline of their own, such as the 5 s and 10 s waits of `tests/test_ui_reactive.py`, and the waits with `THREAD_HANDOFF_BOUND_SECONDS` for a fresh `devops` process in `tests/test_cli_startup_imports.py` and `tests/test_github_session.py`, which can wait through `wait_while_running`: #2138.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

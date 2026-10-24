# Proposal

## Why

Issue #2092: four tests failed on a loaded host, at a load average of 40 to 106, and each passed when it ran alone. Issue #2069 is the same kind of failure in `tests/test_ci.py::test_a_second_signal_to_devops_ci_test_cannot_skip_the_sigkill[SIGINT]`. The project allows no flaky tests. Each failure has its own cause:

- The two end-to-end signal tests of `devops ci test` waited 30 s (`THREAD_HANDOFF_BOUND_SECONDS`) for a fresh `devops` process to start its child. In the full run of the #2060 commit, the start took longer. The SIGTERM case failed with `assert (False, 130, False, False)` and the SIGHUP case with `assert (False, -1, False, False)`. The exit status -1 shows that devops had not yet set its signal handlers 30 s after the test started it.
- The first-signal test also found a defect in the product, in a 50-run check under load of this change: the SIGTERM case failed with `assert (True, 130, True, False)`, and devops exited 300 s after its child started. The run set its handlers with `signal.signal`, and such a handler runs only when the main thread runs bytecode again. A signal that comes just before the event loop starts to wait, or that the kernel hands to another thread, does not wake the loop. The run then took the signal only when its child exited, after the 300 s hold of the grandchild, and the child got no SIGINT.
- The second-signal test found a defect in the product. `asyncio.run` sets its own SIGINT handler, which raises KeyboardInterrupt at a second Ctrl-C between any two bytecodes. When the second Ctrl-C comes just after the stop sends the run's group its SIGINT, the exception comes before the `try` whose `finally` sends the SIGKILL. The stop then skips the SIGKILL, and a group that ignores SIGINT and SIGTERM stays alive.
- `tests/test_ui_reactive.py::test_a_slow_subsystem_does_not_freeze_the_interface` held the k8s fetch for 10 s. On a loaded host the hold ran out before the test looked, and the fetch was then over.
- `tests/test_sandbox_policy_properties.py::test_property_parse_whitelist_entry_reads_ipv6_hosts_and_ports_oracle` ran under the 200 ms deadline of Hypothesis's default profile, which a loaded host can exceed.
- `tests/core/test_clock_contract.py::test_a_ratelimit_window_built_with_the_seam_makes_the_third_call_wait_out_the_period[real-0.03]` measured the window from the first call. `ratelimit` opens the window when it builds it, so a stall between the two made the measured time shorter than the period.

## What Changes

- `devops ci test` takes over Ctrl-C's SIGINT for its run, as it takes over SIGTERM and SIGHUP, and it sets the three handlers with `loop.add_signal_handler`, which writes each signal to the loop's own pipe, so a signal wakes the loop wherever it lands. Each signal only cancels the run's task, so the stop takes a second signal at its next wait and always sends its SIGKILL. A run stopped by Ctrl-C exits as cancelled, 130.
- `tests/support/waits.py` gets `wait_while_running`: a wait for an event of a process that the test started, which ends when the event comes or when the process exits, with no bound of its own. The end-to-end signal tests use it for the start of the fresh `devops`, and wait for its exit with no bound of their own. A process that hangs fails the test at the hang bound of pytest-timeout.
- A new test in `tests/test_ci.py` raises each Ctrl-C at the two points that a loaded host made possible, and shows that the group is killed and that the run exits as cancelled. A second new test hands a SIGTERM to a thread other than the main one while the loop waits, and shows that the stop still sends its SIGINT.
- The UI test holds the k8s fetch until the test releases it, and releases it before the app exits on every path. It waits for the worker with the shared bound.
- Every test run loads Hypothesis's built-in `ci` profile through `--hypothesis-profile=ci` in `addopts`: no deadline and no `too_slow` health check. A new test checks that the property tests of the sandbox policy run under it.
- The clock contract case measures from a seam reading taken just before the window opens. The real case asserts the lower bound that the contract needs. The exact wait is asserted only for the fake clock.
- `docs/TESTING.md` and the docstrings say what changed.
- This change alters behavior that a consumer observes: how `devops ci test` takes a stop signal and a second Ctrl-C. The new capability `ci-test-stop` holds it.
- This change fits in one pull request.

## Capabilities

### New Capabilities

- `ci-test-stop`: how `devops ci test` stops its run when a stop signal comes.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/config/constants.py`: `CONST_CI_RUN_STOP_SIGNAL_NAMES` holds SIGINT, SIGTERM and SIGHUP.
- `src/devops_cli/commands/ci.py`: `_cancelled_by_stop_signals` sets the handlers with `loop.add_signal_handler`; the docstring of `_session_returncode`.
- `src/devops_cli/core/process.py`: the docstrings of `_terminate_process_group_async` and `_spawn_under_stop`.
- `tests/support/waits.py`: `wait_while_running` and the rule for a wait on a process that the test started.
- `tests/test_support_waits.py`: the tests of `wait_while_running`.
- `tests/test_ci.py`: the end-to-end signal tests, the handler tests, the new second Ctrl-C test and the new test of a signal that another thread takes.
- `tests/test_ui_reactive.py`, `tests/core/test_clock_contract.py`, `tests/test_sandbox_policy_properties.py`: the tests of the issue.
- `pyproject.toml` and `tests/test_test_selection.py`: the Hypothesis profile in `addopts` and its pin.
- `docs/TESTING.md`: the Hypothesis profile, the wait for a process that the test started, and the stop signals of `devops ci test`.

## Feasibility

- The pre-commit log of the #2060 commit, a full run of 24 minutes, holds the two failures of the end-to-end signal test with `started` false. A fresh `devops ci test tests/test_x.py` on a quiet host starts its child 0.44 s to 0.51 s after its start. The `strace` of that command shows no lock and no other child before `uv`, so the 30 s went to the start of the interpreter, its imports and the selection.
- A scratch pytest plugin added each stall that a loaded host makes, at the point that each time window covered, and reproduced each failure on the base `c030c1b6`: a 35 s late child start gave `assert (False, 130, False, False)` for SIGTERM and SIGHUP; a 5 ms stall after `ratelimit` built its window gave the message of the issue, `assert (['call', 'ca...False, [0.03]) == (['call', 'ca... True, [0.03])`; a stall of 40 ms before the third call gave `['call', 'call', 'call'] != ['call', 'call', 'wait']`; a parse of 60 ms gave `DeadlineExceeded: Test took 300.99ms`; and a tab switch of 11 s gave `assert ('tab-docker', 1, False) == ('tab-docker', 1, True)`. With the change, each of these runs passes.
- The new test of a signal that another thread takes fails with `signal.signal` handlers: `{'loop waits': True, 'torn down': False}`, and the run ends only when the test stops the child. With `loop.add_signal_handler` it passes.
- A scratch script raised each Ctrl-C in `ci._session_returncode` on the base: the first once the hung child wrote its pids, the second just after the stop's SIGINT. KeyboardInterrupt came out of the run and the group was alive after it. With the change, the run exits as cancelled, 130, and the group is gone.
- CPython 3.14.7, `asyncio/unix_events.py`: `add_signal_handler` calls `signal.set_wakeup_fd` with the loop's own socket, and the loop runs the callback when it reads the signal number from it. `remove_signal_handler` sets the default handler again. The `select.epoll` wait reads pending signals only when the wait ends with EINTR.
- CPython 3.14.7, `asyncio/runners.py`: `Runner._on_sigint` cancels the main task at the first SIGINT and raises KeyboardInterrupt at each later one. `Runner.run` sets that handler only when the SIGINT handler is `signal.default_int_handler`, and puts the default handler back after the run.
- ratelimit 2.2.1, `ratelimit/decorators.py`: `RateLimitDecorator.__init__` sets `self.last_reset = clock()`. A call goes through when `clock() - last_reset` is at least the period, and `sleep_and_retry` waits for the period that remains.
- Hypothesis 6.168.3, `hypothesis/_settings.py`: the built-in `ci` profile sets `deadline=None`, `derandomize=True`, `database=None`, `print_blob=True` and suppresses `HealthCheck.too_slow`. `is_in_ci()` loads it by itself when `GITHUB_ACTIONS` is `true`. The pytest plugin loads the profile that `--hypothesis-profile` names in `pytest_configure`, before it collects the test modules.
- Textual 8.2.8: a thread worker runs in the default executor of the event loop, and the app waits for its thread workers when it shuts down.

## Existing Tool Considered

- Hypothesis's built-in `ci` profile and the `--hypothesis-profile` option of its pytest plugin cover the deadline with no code.
- pytest-timeout's hang bound, which the suite has, fails a process that neither causes its event nor exits.
- asyncio's `loop.add_signal_handler`, through the existing `_cancelled_by_stop_signals`, covers the lost signal and the second Ctrl-C: it replaces the `signal.signal` handlers and their `call_soon_threadsafe`.
- `wait_while_running` is built, as `wait_until` beside it is: no maintained library has a wait that ends when a condition holds or a `subprocess.Popen` exits. Cost: about 3,000 tokens to build, about 1,000 tokens a year to keep and fix, and 15 minutes of elapsed time.
- The change deletes the 10 s hold and wait of the UI test, the 30 s waits of the end-to-end signal tests for the start and the exit of `devops`, and the measurement from the first call in the clock contract case.

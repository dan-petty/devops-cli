# Design

## Context

See `proposal.md` for the failures and their causes. docs/TESTING.md and `tests/support/waits.py` hold the rule: a test waits for an event that the code under test causes, not for a time window, and no test bounds elapsed wall-clock time from above.

## Goals / Non-Goals

**Goals:**

- Each test of #2092 and #2069 passes on a loaded host, with no time window that load can exceed.
- A second Ctrl-C to `devops ci test` can never skip the SIGKILL of the stop.

**Non-Goals:**

- No timeout is made longer, no test is retried or marked as flaky, and no test is skipped.
- The other waits in `tests/` with a deadline of their own, such as the 5 s waits of `tests/test_ui_reactive.py` and the 30 s process bounds of `tests/test_cli_startup_imports.py` and `tests/test_github_session.py`, stay as they are. They are moved to a follow-up issue.

## Decisions

- **The run sets its stop handlers with `loop.add_signal_handler`.** asyncio writes each signal to the loop's own socket through `signal.set_wakeup_fd`, so the loop wakes whichever thread takes the signal and whenever it comes, and runs `cancel` in the loop. A `signal.signal` handler runs only when the main thread runs bytecode again: the epoll wait reads pending signals only when it ends with EINTR, and no EINTR comes when the signal arrives just before the wait or goes to another thread. On exit, `remove_signal_handler` and then `signal.signal` put the previous handlers back.
  - *Rejected alternative:* Keep `signal.signal` and call `signal.set_wakeup_fd` in the run. Evidence: that is what `add_signal_handler` does, with the read of the socket and the call of the callback in the loop.
  - *Rejected alternative:* A short timer that wakes the loop. Evidence: it is a time window, and it delays the stop by up to its period.
- **The run of `devops ci test` takes over Ctrl-C's SIGINT.** `CONST_CI_RUN_STOP_SIGNAL_NAMES` holds SIGINT with SIGTERM and SIGHUP, so `_cancelled_by_stop_signals` replaces `asyncio.run`'s SIGINT handler for the run. Each signal cancels the run's task and raises nothing. The stop takes the cancellation at its next `await`, which is in its `try`, and the `finally` sends the SIGKILL. The run then ends with CancelledError, and `_session_returncode` exits as cancelled, 130, as it did for SIGTERM and SIGHUP.
  - *Rejected alternative:* Send the first signal inside the `try`. Evidence: Python runs a signal's handler between any two bytecodes, so the KeyboardInterrupt can still come inside the `finally`, before `os.killpg`, and skip the SIGKILL.
  - *Rejected alternative:* Block SIGINT with `signal.pthread_sigmask` for the length of the stop. Evidence: the stop lasts up to three graces of `DEFAULT_SHELL_STOP_GRACE_SECONDS`, and a blocked Ctrl-C cannot cut the grace short, which the second-signal test requires.
  - *Rejected alternative:* Catch KeyboardInterrupt around the stop. Evidence: the exception can come at any bytecode, also in the handler that catches it.
- **A wait for an event of a process that the test started has no bound of its own.** `wait_while_running(condition, process)` reads the condition every poll interval until it holds or the process exits, and reads it once more after the exit. The end-to-end signal tests use it for the fake `uv`'s pids, and wait for the exit of `devops` with `Popen.wait()` and no timeout. The start of a fresh interpreter that imports devops-cli is the step that a loaded host stretches the most: 0.44 s to 0.51 s on a quiet host, more than 30 s in the #2060 run. A `devops` that neither starts its child nor exits fails the test at the hang bound of pytest-timeout, as docs/TESTING.md says for an operation that does not stop.
  - *Rejected alternative:* A longer bound, such as ten times `THREAD_HANDOFF_BOUND_SECONDS`. Evidence: it is a time window that a loaded host can still exceed, and #2092 does not permit a longer timeout as the fix.
  - *Rejected alternative:* Run the command in the test process. Evidence: the tests check what the `devops` process does with a signal: the handlers of `asyncio.run`, the stop of the group and the exit status. Only a process of its own has them.
  - *Rejected alternative:* Fork the test process instead of a fresh start. Evidence: the test process has threads, and a fork of a process with threads can deadlock in the child.
- **The UI test holds the k8s fetch until the test releases it.** The hold has no bound of its own, so it outlives every wait that observes it. A `finally` inside the app's context releases it on every path, because Textual waits for its thread workers when it shuts down. The wait for the worker to start uses `THREAD_HANDOFF_BOUND_SECONDS`.
  - *Rejected alternative:* A hold of twice the bound that records whether it ran out, as another test of the module does. Evidence: it keeps a time window, which the release in the `finally` makes unnecessary.
- **Every test run loads Hypothesis's built-in `ci` profile.** `addopts` gets `--hypothesis-profile=ci`, which GitHub Actions already loads by itself. The profile has no deadline and no `too_slow` health check, so the time of an example cannot fail a property. It is derandomized, so a local run tries the examples that CI tries.
  - *Rejected alternative:* `deadline=None` in the settings of each module. Evidence: five modules already do this, and a new property module can forget it. The profile covers every property test with one setting.
  - *Rejected alternative:* A project profile registered in a support plugin. Evidence: it repeats the built-in profile in code of our own.
- **The real clock contract case asserts the lower bound.** The test reads `clock_seam.monotonic()` just before it builds the window, and stamps each call with the same seam. `ratelimit` lets the third call through only when the period has passed since the window opened, so the stamp of the third call is always at least the period after that reading. The fake clock moves only when the seam waits, so its case also asserts the one wait of the whole period. A real clock can pass the period during a stall before the third call. That call then goes through with no wait, which the contract permits, so the real case does not assert the wait.
  - *Rejected alternative:* A longer period for the real case. Evidence: a stall can still exceed it.
  - *Rejected alternative:* Read `window.last_reset`. Evidence: it is internal state of `ratelimit`; the seam reading before the build gives the same lower bound.

## Risks / Trade-offs

- [A Ctrl-C to `devops ci test` no longer raises KeyboardInterrupt from the run] → The run exits as cancelled, 130, with the same exit status as before. No caller catches the KeyboardInterrupt.
- [The first end-to-end signal test still depends on the product's grace] → The fake `uv` must run its SIGINT trap within `DEFAULT_SHELL_STOP_GRACE_SECONDS` of the SIGINT, or the SIGTERM ends it before its teardown. A test cannot remove that window without a setting for the grace, which the product does not have. No run failed for that reason.
- [A broken mount of the dashboard app can hang the UI test] → A hold with no bound keeps the thread worker alive if the app fails while it starts. pytest-timeout then fails the test, naming it.

# Design

## Decisions

- **One helper for each run that a stop signal ends.** `_until_stopped(run)` cancels `run` on Ctrl-C, SIGTERM or SIGHUP through `_cancelled_by_stop_signals`. `_run_in_own_session` (`devops ci test`) and the gate run of `all_checks` both use it. The stop of each row is the existing stop of `run_subprocess_async`, which stops the process group of the row.
- **The row names itself.** `_execute_check_async` prints the stopped line in its `except asyncio.CancelledError` branch and raises the cancellation again. Thus each row that ran at the signal gets a line, and a row that ended before gets its usual line.
- **The limit is in the hook.** Each `devops ci` hook of the pre-push stage starts with `timeout <seconds>`. The hook owns its limit, and the structural test reads it there.
- **The budget of the push.** 20 s (fetch) + 40 s + 30 s + 25 s = 115 s, less than 120 s. The 25 s cover the start of pre-commit, the transfer to GitHub, and the stop of two hooks after their limits. A stop takes at most three steps of 3 s (`DEFAULT_SHELL_STOP_GRACE_SECONDS`).

## Rejected alternatives

- **`devops ci --timeout` and the setting `ci.check_timeout_seconds` (the design of the issue).** They do what `timeout` does, with an option, a setting, an environment variable and their documents to keep. They also leave the defect: any other stop signal still leaves the rows running.
- **`timeout --foreground`.** It signals only `uv`, so it depends on the signal forwarding of uv. The default mode signals the whole process group of `timeout`, as `branch-current` uses it.
- **A limit for each row in `CheckSpec`.** #4683 plans it for the test row and the index build. The pre-push stage needs one limit for each hook, not for each row.

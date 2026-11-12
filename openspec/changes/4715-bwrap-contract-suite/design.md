# Design

## Decisions

- **`ps` reads the process table.** The two process-tree tests need to see each process of the host, in each namespace below it. `ps -e -ww -o args=` gives the full command line of each process, and the test looks for its temporary path in the text. `@pytest.mark.live("ps")` lets the floor start it. The guard that keeps the test process out of `/proc` does not change.
- **The row uses the host check of the sandbox executor.** `SandboxToolExecutor.host_refusal()` checks that bubblewrap and prlimit are installed and that bubblewrap can make a sandbox with `prlimit -- true` in it. It runs one time for each executor. A check of the binary alone passes on Ubuntu 24.04 when bubblewrap is installed and AppArmor refuses it a user namespace, and the row would then fail 55 tests for a cause of the host.
- **A skipped row passes and shows the cause.** `CheckResult.skipped` holds the cause, the summary shows `skipped: <cause>` with no duration, and `CICachedCheck.skipped` keeps it, so a cached verdict does not show the row as passed. The skip is no failure: the host cannot give what the row needs, as `docs/TESTING.md` asks for a test that needs a capability of the host.
- **The host check runs in a thread.** It starts bubblewrap with a timeout of 30 s, and `asyncio.to_thread` keeps the other rows running while it waits.
- **One process.** The row passes `-n 0`. The 55 tests take 3.6 s in one process, and xdist would start one interpreter for each CPU beside the test row of a full gate.
- **Gate tests do not read the bubblewrap of the host.** `sandbox_host` puts stand-ins for bubblewrap and prlimit first on PATH for each test that uses `ci_root` or `ci_head`, and the process fake answers the check. A full gate in a test runs the row on every host.

## Rejected alternatives

- **Let a `bwrap` test open `/proc/<pid>/cmdline` through the host path guard.** It adds an exemption to the floor to make a check pass. The project rule (`docs/SDLC.md`, "Where a Check Runs") refuses an escape or a special case, and `ps` gives the same data with no change to the floor.
- **`pgrep -f <path>`.** pgrep reads its pattern as an extended regular expression. A temporary path needs escaping, and `re.escape` writes escapes, such as `\-`, that POSIX leaves undefined.
- **`HostSandbox().is_available()` as the host check, as the issue text says.** It reads only that the binary is a file. On a host where bubblewrap cannot make a user namespace, the row would run and fail. The check of the sandbox executor gives the cause that a review gives on the same host.
- **Add `bwrap` to the `--skip` list of `Static Analysis`.** The row already skips on the runner with the cause, at the cost of one file check. The change would also touch `ci.yml`, which other open work changes.
- **Install bubblewrap on the runner.** The owner rule is that a GitHub-hosted runner gets no package install or host change.

# Proposal: #6048

## Why
`tests/telemetry/test_sigterm_export.py::test_a_process_with_the_default_action_exports_then_ends_by_sigterm` hung to the 600 s bound of pytest-timeout in `Service Image Tests`. It held the certifi security fix #6028, because Renovate merges a security fix only when every check of its branch passes (#6031). The child process of the test waits for SIGTERM in `signal.pause()`. CPython runs a Python signal handler only between two bytecodes. A SIGTERM that comes after the last check for signals and before the `pause` system call sets only the flag of the C handler. The pause then waits for a second signal that never comes. The SIGTERM handler of the product is not the cause.

Closes #6048.

## What Changes
- The child waits for SIGTERM on the read end of a pipe that it gives to `signal.set_wakeup_fd`. The C handler writes a byte to that pipe, so the read returns also for a signal that came before the read. The Python handler then runs as the read returns.
- The test waits for the line of the child with `wait_while_running` on a file, as `docs/TESTING.md` asks for an event of a process that the test started. It sends SIGTERM after any line, and it kills and reaps the child in a `finally` block. A child that writes another line or exits first fails the test at once, and the assertion names its output and its exit status.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The change is in one test. The SIGTERM export of `src/devops_cli/telemetry/sigterm_export.py` does not change.

## Impact
- `Service Image Tests` ends this test in about 1.5 s again, so a Renovate update of the image or of a Python package is not held by it.
- No command, setting, manifest or product code changes.

## Feasibility
- The stack of each hang shows the test in `child.wait()` after it sent SIGTERM (jobs 133095388623, 133581940030, 133637219622 and 133648554544).
- A stress run of the old child, 24 at a time on a host with 16 CPUs, hung in 41 of 600 runs. Each hung child waited in `__do_sys_pause` with SIGTERM caught, not pending, not blocked and not ignored, and it had recorded no export. The same child with the wakeup pipe hung in 0 of 1,200 runs.
- `src/` holds no `signal.pause` call.

## Existing Tool Considered
`signal.set_wakeup_fd` of the Python standard library covers the need: its documented use is to wake a blocking wait for a signal that came before the wait. The change builds no tool and adds no dependency. Cost: about 150k tokens and 1 hour, most of it for the diagnosis.

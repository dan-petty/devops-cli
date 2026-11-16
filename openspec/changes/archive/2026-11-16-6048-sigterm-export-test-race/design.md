# Design

## Decisions

- The child waits with `os.read` on the read end of its wakeup pipe (`signal.set_wakeup_fd`). The C handler writes the signal number to that pipe, so a SIGTERM that comes before the read leaves a byte that ends the read at once. A SIGTERM that comes during the read ends it with `EINTR`. In both cases CPython runs the Python handler as the call returns, and the handler exports, sets the default action and sends SIGTERM again.
- The test waits for the line of the child with `wait_while_running` on a file, with no bound of its own, and waits for the exit with `child.wait()`, also with no bound (`docs/TESTING.md`, waits for a process that the test started). A child that hangs fails at the bound of pytest-timeout, and the `finally` block kills and reaps it.
- The test sends SIGTERM after any line, not only after `ready`. A child that writes another line first then ends, and the assertion names the line, in place of a wait to the bound of pytest-timeout.

## Rejected alternatives

- A loop of short sleeps in the child in place of `signal.pause()`: it also ends the hang, because each sleep returns and the next check runs the handler. But it is a poll, and the wakeup pipe of the standard library removes the race with no poll.
- `signal.sigwait` or `signal.sigtimedwait` in the child: they take the signal without the Python handler, so the child would not run the export that the test checks.
- A shorter `@pytest.mark.timeout` or a `timeout=` on the waits: it makes the hang shorter but keeps it, and `docs/TESTING.md` forbids a deadline of its own on a wait for a process that the test started.
- A change of `SigtermExport` in `src/`: the handler is correct. Each hung child had recorded no export, so the Python handler had not run.

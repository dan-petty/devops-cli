# Design

## Context

MCP tools execute devops CLI operations either as external subprocesses or in-process via `InProcessDispatcher`.
In-process execution eliminates subshell invocation overhead.
However, `_dispatch_typer` executed commands directly on the calling thread without applying the timeout budget.
A command that hangs in-process blocks the tool indefinitely.

## Architecture

1. **Timeout Parameter Propagation**:
   - `InProcessDispatcher.dispatch` accepts `timeout` (defaulting to `DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS`).
   - `dispatch` passes `timeout` and `cmd` to `_dispatch_typer`.

2. **Bounded Thread Execution**:
   - `_dispatch_typer` runs `runner.invoke` in a daemon worker thread.
   - The dispatch thread waits on the worker thread with `t.join(timeout=timeout)`.
   - If the worker finishes within budget, `_dispatch_typer` returns the result normally.
   - If the worker thread is still alive after `timeout`, `_dispatch_typer` records a warning and returns `(124, f"Command timed out after {timeout} seconds: {target}")`.
   - Before returning, standard streams (`sys.stdout`, `sys.stderr`, `sys.stdin`) are restored.
   - The `_isolate_child_stdio()` context manager on the dispatch thread restores operating system file descriptors 1 and 2.

3. **Subprocess Timeout Alignment**:
   - `_dispatch_subprocess` catches `subprocess.TimeoutExpired` and returns `124, f"Command timed out after {timeout} seconds: {' '.join(cmd)}"`.

## Rejected Alternatives

- **Spawning all commands as child processes with `run_subprocess`**:
  Rejected. Starting a new Python process for every tool call adds 300-500ms of startup latency. In addition, the test environment hermetic floor refuses `devops` subprocess execution without fakes.
- **Using `signal.SIGALRM`**:
  Rejected. `signal.alarm` operates only on the main interpreter thread. FastMCP executes tool functions inside worker threads, where `signal.alarm` raises `ValueError`.
- **Using `ctypes` to raise an asynchronous exception in the worker thread**:
  Rejected. Asynchronous thread interruption in CPython does not interrupt sleep or native system calls. It can also corrupt internal interpreter locks.

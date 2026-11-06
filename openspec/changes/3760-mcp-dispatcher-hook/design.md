# Design

## Context

See proposal.md (#3760). An MCP tool builds a `uv run devops ...` command line and calls `_run_mcp_cmd`. `_run_mcp_cmd` asks `get_mcp_dispatcher()` for the dispatcher, which runs the command in the same process and returns an exit code and text. The tool then masks secrets, bounds the text, and raises `ToolError` for a non-zero code.

## Goals / Non-Goals

**Goals:**
- One seam where a test reads the command line, the timeout and the environment of a tool.
- No code in `ai/mcp/` that runs a program.
- Tests that run the real tool and the real `_run_mcp_cmd`, so masking, bounding and the exit-code mapping stay under test.

**Non-Goals:**
- Splitting or renaming the MCP test files (child F of #1330).
- Replacing the patches of other test packages.

## Decisions

### 1. A hook on the singleton, not a second factory
- **Decision**: `install_mcp_dispatcher(dispatcher)` stores the dispatcher in the module singleton under the existing lock. `reset_mcp_dispatcher()` clears it. The floor already resets the singleton after each test.
- **Alternative considered**: patch `get_mcp_dispatcher`. *Rejected*: it patches an internal name, which the testing rules forbid.

### 2. A `Protocol` for the seam
- **Decision**: `McpDispatcher` has `subscriptions` and `dispatch`. `InProcessDispatcher` and `DispatcherFake` both satisfy it, and a type checker proves it.
- **Alternative considered**: subclass `InProcessDispatcher` in the fake. *Rejected*: the fake would inherit the Typer path and could run a real command by mistake.

### 3. Refuse a command line that is not a `devops` one
- **Decision**: `devops_sub_args` raises `ValidationError`. The dispatcher and the fake both call it before they record or run anything.
- **Alternative considered**: keep the subprocess branch. *Rejected*: no caller reaches it, so only tests ran it (dead code).

### 4. The fake keeps the rules of the real dispatcher
- **Decision**: The fake adds the text `Success` or `no output captured` for an empty answer, as the real dispatcher does, and answers a timeout with exit code 124 and the real text. The contract suite runs each case on both sides. Real-side cases register hidden commands on the Typer app and start no program.

### 5. The fake needs its own `ResourceSubscriptionManager`
- **Decision**: `_run_mcp_resource` calls `get_mcp_dispatcher().subscriptions.notify(...)`. So the fake holds a real `ResourceSubscriptionManager`.

## Risks / Trade-offs

- The fake can drift from the real dispatcher. The contract suite runs both and catches drift.

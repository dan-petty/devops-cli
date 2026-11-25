# Design

## Decisions

- **Run the three tool calls across three sequential `ModelScript` turns**: Replace `tool_calls(same, same, other)` at `tests/roadmap/implement/test_roadmap_implement_step_trace.py:193` with `tool_calls(same), tool_calls(same), tool_calls(other)`. Because each model reply holds one `ToolCallPart`, `pydantic_ai` awaits completion of each command before requesting the next turn, eliminating task-scheduling races in `TraceEventKind.TOOL` ordering while preserving the exact assertions `digests[0] == digests[1] != digests[2]`, digest length 12, and `"sentinel" not in trace.encode()`.

## Rejected alternatives

- **Keep `tool_calls(same, same, other)` in one turn and replace the positional assertion with `Counter(digests)`**: Weakens the check on ordered trace appending (`ImplementTrace.events` records calls in execution order, as `src/devops_cli/roadmap/implement/implement_step.py:494` and `tests/roadmap/implement/test_roadmap_implement_step_trace.py:161` rely on separate `tool_calls(...)` turns).
- **Disable concurrent tool execution globally in `implement_step.py`**: Changes production runtime concurrency for a test-only ordering race when `tests/roadmap/implement/test_roadmap_implement_step_trace.py:183` did not intend to test parallel tool execution.

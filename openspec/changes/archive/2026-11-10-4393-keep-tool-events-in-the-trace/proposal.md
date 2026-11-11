# Proposal: #4393

## Why

The trace of a long implement run (`implement.trace`, `devops roadmap explain <issue> --trace`) holds only model events. The tool events and the check events of the run are gone, so nobody can see whether the agent edited a file, repeated a call or got a failing check. Closes #4393.

`ImplementTrace.encode` drops the oldest events until the text fits `CONST_ROADMAP_IMPLEMENT_TRACE_CHARS` (8,192 characters). The tool events and the check events are added while the turn runs, but `_trace_replies` in `implement_step.py` adds the model events after the turn ends. In a turn of 100 requests the trace holds all the tool events first and all the model events last, so the bound drops the tool events and keeps the model events.

## What Changes

- A model event is added when its reply comes, in a `Hooks` method of `ToolCallLog` (`after_model_request`). The events of a run then stand in the order of the run: a model event, then the tool calls that it asked for, then the next model event.
- When the encoded trace is longer than the bound, `ImplementTrace.encode` drops the oldest model events first. Only when no model event is left does it drop the oldest of the other events. The kept events stay in the order of the run, and `dropped` counts every event that goes. The tool, check, retry and attempt events show the progress of the run; `implement.spend` keeps the tokens of the run.
- `_trace_replies` adds an event only for a reply that has none: the reply that the output cap cuts never reaches the hook.
- A `tool` event of a `shell` call holds `status`, the exit status of the command, when the shell reports one. The shell of the harness ends the result of a command with the line `{"pid": <n>, "exit_code": <n>}` that its supervisor wrote. A command that has not ended has no status.
- `devops roadmap explain --trace` shows the exit status in the line of a shell call.
- An event still holds only counts, digests, names, outcomes and exit statuses: no argument, no output, no secret, no private host name.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: The events of a trace stand in the order of the run; A shell call in a trace holds its exit status
- `roadmap-implement-job`: The job keeps the trace of its run (the bound drops the oldest model events first)
- `roadmap-explain`: The trace option prints a shell call with its exit status

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_tool_log.py`, `src/devops_cli/roadmap/implement/implement_trace.py`, `src/devops_cli/roadmap/implement/implement_step.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_trace.py`, `tests/roadmap/implement/test_roadmap_implement_step_trace.py`, `tests/roadmap/test_roadmap_explain.py`
- Specs: `openspec/specs/roadmap-implement-step/spec.md`, `openspec/specs/roadmap-implement-job/spec.md`, `openspec/specs/roadmap-explain/spec.md`
- Documents: `docs/roadmap/implement.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/CLI_REFERENCE.md` (generated)
- The size bound does not change. The record block stays far under the 65,536 characters of an issue body.

## Feasibility

- Command output: `devops roadmap explain 3443 --trace` shows 66 `model` events and `81 earlier event(s) are not kept`, with no `tool` event and no `check` event. This is the failure that the issue names.
- Library source (`pydantic_ai` 2.59.0): `Hooks(after_model_request=...)` runs after each model response, and the step already uses it to count tokens (`limit_hooks`). The response in the hook is the object that `capture_run_messages` returns, so the identity of a reply tells the step that its event exists. A test with two scripted replies asserts one event for each.
- Harness source and a real run (`pydantic_ai_harness` 0.59.0, `Coder` with `LocalWorkspace`): the `shell` tool returns the output, the lines `PID:`, `Output:` and `Status:`, and last the status line. The run printed `{"pid": 99068, "exit_code": 0}` for `git status --short` and `{"pid": 99065, "exit_code": 128}` for a failing `git rev-parse`. `ShellToolset.call_tool` keeps the tail of a long result, so the status line stays. The tool does not report the status in any other field of the result. The harness event `CommandFinishedEvent` carries `exit_code` too, but it reaches the step on the event stream with no ordering against the tool result, so the step reads the result.
- A step in the test suite cannot run the real shell (the process edge is faked), so the tests give a fake `shell` tool that returns a result of the same form.

## Existing Tool Considered

The need is a change of order in code that the project owns. No library keeps a bounded trace of an agent run in the job record: Logfire and OpenTelemetry spans hold the same facts, but the job record is where `explain --trace` reads, and the Job's checkout and spans are gone when the Job ends. Cost to build: about 25k tokens, about 1 hour. The change deletes the post-turn pass over `messages` in `_trace_replies`.

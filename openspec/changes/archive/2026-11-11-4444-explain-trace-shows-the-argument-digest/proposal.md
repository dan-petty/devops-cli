# Proposal: #4444

## Why

`devops roadmap explain <issue> --trace` does not show the digest of the argument of a tool call. The `tool` event in `implement.trace` holds the digest in the field `digest`, but `_event_line` in `src/devops_cli/roadmap/explain.py` does not read it. So a reader cannot see that the model made the same call two or more times. Issue #4393 asked for this in its criterion "Render tool and check details", and pull request #4436 did not deliver it. Closes #4444.

## What Changes

- The line of a `tool` event shows the digest of its argument after the program, for example `group 1: tool shell (program git) [argument abc123abc123], ok (exit status 0)`.
- A `tool` event with no digest shows no argument part, so a trace from before the digest still prints.
- The text of the part is `explain_trace_tool_digest` in `RoadmapMessages`.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-explain`: The trace option prints the argument digest of a tool call (added)

## Impact

- Code: `src/devops_cli/roadmap/explain.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_explain.py`
- Specs: `openspec/specs/roadmap-explain/spec.md`
- Documents: `docs/roadmap/implement.md`
- The trace keeps the same fields and the same bound. The digest is 12 hexadecimal characters of the SHA-256 of the masked argument, so the line shows no argument and no secret.

## Feasibility

- Source on `main`: `ImplementTrace.tool_call` in `src/devops_cli/roadmap/implement/implement_trace.py` keeps the digest in the field `digest`. The `TraceEventKind.TOOL` case of `_event_line` reads `tool`, `program`, `outcome`, `status` and `reason`, and not `digest`. `explain_trace_tool` is `"{step}: tool {tool}{program}, {outcome}{status}{reason}"`.
- Test output on the base: the two changed tests of `tests/roadmap/test_roadmap_explain.py` fail with `'group 1: tool shell (program git), ok (exit status 128)' != 'group 1: tool shell (program git) [argument abc123abc123], ok (exit status 128)'`.

## Existing Tool Considered

No tool applies: the change is one field in a line of text that the project owns. Cost to build: about 10k tokens and 30 minutes.

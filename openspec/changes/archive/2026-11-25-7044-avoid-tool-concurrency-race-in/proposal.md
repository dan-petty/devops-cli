# Proposal: #7044

## Why

`test_the_same_call_twice_has_one_digest_and_no_event_holds_the_command` (`tests/roadmap/implement/test_roadmap_implement_step_trace.py:183`) places `same`, `same`, and `other` in one `tool_calls(...)` turn (`tests/roadmap/implement/test_roadmap_implement_step_trace.py:193`) and asserts positional order `assert digests[0] == digests[1] != digests[2]` (`tests/roadmap/implement/test_roadmap_implement_step_trace.py:198`). Because `pydantic_ai` executes tool calls in one reply concurrently and `ImplementStep._note` (`src/devops_cli/roadmap/implement/implement_step.py:494`) logs each `TraceEventKind.TOOL` upon completion, `other` (`8493027a96ad`) intermittently finishes before the second `same` (`2e20f17b55e7`) (#7044).

## What Changes

- Change `script` in `tests/roadmap/implement/test_roadmap_implement_step_trace.py:193` from `ModelScript(tool_calls(same, same, other), say("Done."))` to sequential model turns `ModelScript(tool_calls(same), tool_calls(same), tool_calls(other), say("Done."))`, keeping `tests/roadmap/implement/test_roadmap_implement_step_trace.py:198` (`assert digests[0] == digests[1] != digests[2]`) deterministic while still exercising two identical commands and one distinct command without leaking sentinel arguments.
- This change modifies only test ordering with no observable consumer or runtime behavior change (`skip_specs: true`).
- Fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: `tests/roadmap/implement/test_roadmap_implement_step_trace.py`

## Feasibility

- Inspected `tests/roadmap/implement/test_roadmap_implement_step_trace.py:183-200`, `tests/support/model_script.py:42-49` (`tool_calls(*calls)` constructs one `ModelResponse` containing all `ToolCallPart` entries concurrently), `src/devops_cli/roadmap/implement/implement_step.py:494`, and CI failure logs from job `138903829621` confirming `same` hashes to `2e20f17b55e7` and `other` hashes to `8493027a96ad`.

## Existing Tool Considered

Uses the existing `ModelScript` and `tool_calls` helper (`tests/support/model_script.py:42`). No external dependency applies, and no internal file is deleted.

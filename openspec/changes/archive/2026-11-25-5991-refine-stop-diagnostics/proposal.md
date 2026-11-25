# Proposal: #5991

## Why
When a refine investigation stops with `UnexpectedModelBehavior` (such as on `local/qwen3.8:27b`), `run_error_message` masks quoted text into `<text>` and omits the failed tool name, registered tool list, structured-output mode, and response part kinds from `refine.failure` and the warning log, making model compatibility diagnosis impossible from job records alone.

## What Changes
- Record diagnostic stop metadata (`tool_name`, `registered_tools`, `output_mode`, `part_kinds`, `stop_reason`) on `InvestigationStopped` in `src/devops_cli/roadmap/refine/refine_investigation.py`.
- Emit `stopped.stop_reason` in refine job failures and warning logs (`src/devops_cli/roadmap/refine/refine.py`) whenever a model response or retried tool call stops the investigation, while keeping existing masked `message` bounds and direct exception compatibility intact.
- Add offline `FunctionModel` tests in `tests/roadmap/refine/test_roadmap_refine_investigation.py` covering an unknown `<text>` tool call and `NativeOutput` receiving plain text.

## Capabilities
- `roadmap-refine`

## Impact
Maintainers investigating stopped refine runs can see directly in `refine.failure` and warning logs which tool exceeded retries, which tools were registered, what output mode ran, and what part kinds the model emitted, without storing raw model reply text or secrets.

## Feasibility
Confirmed on `origin/main`: `_stopped_outcome` (`refine_investigation.py:545`) computes `cause = stop_cause(...)` but constructs `InvestigationStopped` with only `run_error_message(stopped)`, discarding `cause.detail`, `tool_names`, `output_type`/schema mode, and last reply part kinds from the emitted stop reason in `refine.py:3373, 3945`.

## Existing Tool Considered
Uses the existing `pydantic_ai` output wrappers (`NativeOutput`, `PromptedOutput`, `ToolOutput`), schema `mode` inspection, `ModelResponse.parts[].part_kind`, and `FunctionModel` test double (`pydantic/pydantic-ai`, `in-use`); no external library needed.

# Design

## Decisions
- Keep `InvestigationStopped.message` equal to `run_error_message(stopped)` so existing contracts on line-1 length caps (`CONST_ROADMAP_RUN_ERROR_CHARS`), token redaction, and message equality tests remain unchanged.
- Expose `tool_name`, `registered_tools`, `output_mode`, `part_kinds`, and `stop_reason` on `InvestigationStopped`. Populate `output_mode` via `type(output_type).__name__` when wrapped (`NativeOutput`, `PromptedOutput`, `ToolOutput`) else the agent's `_output_schema.mode` (falling back to `type(output_type).__name__`).
- Include the diagnostic suffix (`tool=...`, `registered=[...]`, `output_mode=...`, `parts=[...]`) in `stopped.stop_reason` whenever the run recorded a `ModelResponse` or a retried/invalid tool name, and format both `_job_failure` (`refine.py:3373`) and warning logs (`refine.py:3945`) with `stopped.stop_reason`.
- Mask `tool_name` with `bounded_text` and include no reply text or `tool_call_id` so existing secret/prompt-isolation guarantees hold.

## Rejected alternatives
- Replacing `InvestigationStopped.message` directly: rejected because existing invariant tests require `len(stopped.message) == CONST_ROADMAP_RUN_ERROR_CHARS` and exact output-retry strings.
- Parsing `stopped.message` string for tool names: rejected because pydantic-ai formats and quotes tool names in an unguaranteed error template that `run_error_message` sanitizes.
- Raising retry limits above `CONST_ROADMAP_REFINE_INVESTIGATION_RETRIES` (2): rejected because it hides incompatible tool/output behavior without revealing why it failed.

# Task 123: LLM Structured Output Retry and JSON Schema Repair Engine

**Issue**: [#123](https://github.com/dan-petty/devops-cli/issues/123)
**PR**: [#230](https://github.com/dan-petty/devops-cli/pull/230)
**Status**: In Review
**Milestone**: `v0.2.19`
**Priority**: `priority/p2-medium`
**Scope**: `scope/ai`

---

## 1. Description & Objectives

Open-weight local and remote language models (such as `gemma4:26b` or `qwen2.5:32b`) occasionally emit slightly malformed JSON, markdown fences (` ```json `), unclosed brackets, trailing commas, or incomplete schemas during structured generation. In the past, this led to immediate failure with `AIClientError: Response validation failed for model '...'` without error reflection back to the model or local JSON repair.

This task implements an automated structured output and JSON schema repair pipeline in `devops_cli.ai.client`:
1. **Local Syntax Repair**: Strips thinking blocks and markdown fences, applying `json_repair` to recover trailing commas, unclosed brackets, single quotes, and wrapped objects without round-trip latency.
2. **Pydantic Validation Engine**: Strictly validates parsed payloads against target `BaseModel` schemas via `TypeAdapter` and `model_validate`.
3. **Dynamic Reflection Retry Loop**: When validation fails, constructs dynamic reflection messages containing bounded error details (`ChatMessage(role="user", content=...)`) to prompt the model for self-correction with exponential backoff up to `DEFAULT_STRUCTURED_OUTPUT_MAX_RETRIES = 2`.
4. **Telemetry & Observability**: Emits OpenTelemetry metrics (`ai.client.structured_success`, `ai.client.structured_repair_success`, `ai.client.structured_retry_count`, `ai.client.structured_validation_failure`) and traces spans under `ai.client.chat_structured`.

---

## 2. Key Deliverables

- `src/devops_cli/config/defaults.py`: `DEFAULT_STRUCTURED_OUTPUT_MAX_RETRIES = 2`, `DEFAULT_STRUCTURED_RETRY_BACKOFF_SECONDS = 0.5`.
- `src/devops_cli/config/constants.py`: `CONST_ERROR_CODE_STRUCTURED_VALIDATION`, `CONST_MAX_ERROR_DETAIL_LENGTH = 256`, and structured telemetry metric constants.
- `src/devops_cli/ai/client/structured.py`: `StructuredOutputMixin` implementing `chat_structured`, `_repair_and_validate_payload`, `_build_reflection_message`, and retry logic with cyclomatic complexity $M \le 5$ and nesting depth $\le 3$.
- `src/devops_cli/ai/client/unified.py`: `LLMClient` inherits `StructuredOutputMixin`.
- `tests/test_ai_client_structured.py`: Comprehensive test suite verifying clean JSON extraction, markdown fence stripping, malformed JSON repair, reflection retries, retry exhaustion, and telemetry.

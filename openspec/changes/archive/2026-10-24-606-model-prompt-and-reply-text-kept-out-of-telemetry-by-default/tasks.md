# Tasks

## 1. Implement failing tests for telemetry LLM content gating and host scrubbing

- [x] 1.1 Write tests verifying that prompt preview and response preview are omitted when capture is off, and present when capture is on.
- [x] 1.2 Write tests verifying Logfire configuration with `PRIVATE_HOST_PATTERNS` scrubbing and `instrument_pydantic_ai(include_content=...)`.
- [x] 1.3 Verify tests fail before implementation.

## 2. Implement configuration and telemetry changes

- [x] 2.1 Add `capture_llm_content` to `TelemetryConfig` in `src/devops_cli/config/settings.py` and `src/devops_cli/config/options.py`.
- [x] 2.2 Define `PRIVATE_HOST_PATTERNS` beside `_SECRET_PATTERNS` in `src/devops_cli/security/sanitizer.py`.
- [x] 2.3 Update `OTelTelemetryClient` and `get_tracer` in `src/devops_cli/telemetry/tracer.py` to support `capture_llm_content`.
- [x] 2.4 Update `LogfireBridge.configure` in `src/devops_cli/telemetry/logfire.py` to apply scrubbing options and pass `include_content`.
- [x] 2.5 Gate `llm.prompt_preview` and `llm.response_preview` in `src/devops_cli/ai/client/unified.py`.
- [x] 2.6 Verify that all tests pass.

## 3. Documentation and sync

- [x] 3.1 Update documentation in `src/devops_cli/docs/generator.py` and `docs/CONFIGURATION.md`.
- [x] 3.2 Run `uv run devops docs generate --sync-readme` and verify `uv run devops docs check`.
- [x] 3.3 Run `uv run devops ci` quality gate.

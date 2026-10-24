# Proposal

## Why

Issue #606: By default, Logfire instrumentation and native AI dispatch spans recorded prompt and response text in telemetry. Pydantic validation spans and native `ai.llm.dispatch` spans contained prompt and response previews without masking. An internal hostname or private network address in a prompt could enter telemetry export. Telemetry must keep prompt text and reply text out of traces and spans by default.

## What Changes

- Add the configuration setting `telemetry.capture_llm_content: bool = False`.
- When `telemetry.capture_llm_content` is false, native `ai.llm.dispatch` spans omit `llm.prompt_preview` and `llm.response_preview`.
- When `telemetry.capture_llm_content` is true, native `ai.llm.dispatch` spans include `llm.prompt_preview` and `llm.response_preview`.
- Define `PRIVATE_HOST_PATTERNS` beside `_SECRET_PATTERNS` in `src/devops_cli/security/sanitizer.py`.
- Configure Logfire with `scrubbing=logfire.ScrubbingOptions(extra_patterns=PRIVATE_HOST_PATTERNS)`.
- Configure Logfire to call `logfire.instrument_pydantic_ai(include_content=False)` when `telemetry.capture_llm_content` is false.
- Update documentation and configuration schemas to document `telemetry.capture_llm_content`.

## Capabilities

### New Capabilities

- `llm-telemetry-content`: Controls the recording of prompt and reply content in OpenTelemetry and Logfire spans, and scrubs private host patterns.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/config/settings.py`, `src/devops_cli/config/options.py`, `src/devops_cli/security/sanitizer.py`, `src/devops_cli/telemetry/tracer.py`, `src/devops_cli/telemetry/logfire.py`, `src/devops_cli/ai/client/unified.py`, and `src/devops_cli/docs/generator.py`.
- Documents: `docs/TELEMETRY.md`, `docs/CONFIGURATION.md`.
- Tests: `tests/test_telemetry_llm_content.py`, `tests/test_telemetry_logfire.py`.

## Feasibility

- Logfire: `logfire.ScrubbingOptions` accepts `extra_patterns: Sequence[str]`. `logfire.instrument_pydantic_ai` accepts `include_content: bool`.
- Sanitizer: `src/devops_cli/security/sanitizer.py` declares credential patterns. `PRIVATE_HOST_PATTERNS` adds internal domain and private network patterns.
- AI client: `_dispatch_messages` and `_set_response_span_attributes` in `src/devops_cli/ai/client/unified.py` set preview attributes. The tracer gates preview attributes with `capture_llm_content`.
- Validation: `is_loopback_or_private_host` in `src/devops_cli/core/validation.py` classifies internal hosts and private network addresses correctly.

## Existing Tool Considered

OpenTelemetry semantic conventions and Logfire built-in scrubbing options provide standard interfaces for telemetry redaction. The change uses standard Logfire `ScrubbingOptions` and `instrument_pydantic_ai(include_content=...)`. No custom scrubber engine is created.

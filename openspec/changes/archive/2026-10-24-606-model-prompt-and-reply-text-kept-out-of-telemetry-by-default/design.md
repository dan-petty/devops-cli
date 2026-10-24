# Design

## Context

devops-cli uses OpenTelemetry for distributed tracing and Logfire for structured AI observability. When a user runs commands that invoke AI models, spans record execution details. Without explicit gating, prompt text and response previews enter trace spans and Logfire events.

## Goals / Non-Goals

**Goals:**

- Keep model prompts and responses out of telemetry spans by default.
- Allow users to opt in to prompt and response capture with `telemetry.capture_llm_content`.
- Scrub private host names and addresses from Logfire spans with `PRIVATE_HOST_PATTERNS`.
- Preserve `agent.prompt` and `agent.response` in `devops telemetry test` because they use fixed test strings.

**Non-Goals:**

- Collector-side redaction pipelines (out of scope for client configuration).
- Changes to token usage metrics or turn counters.

## Decisions

- **Use a dedicated boolean configuration setting `telemetry.capture_llm_content`.** The setting lives under the `telemetry` section in `Settings` and defaults to `False`.
- **Pass `include_content` to `logfire.instrument_pydantic_ai`.** When `telemetry.capture_llm_content` is false, pass `include_content=False`. When true, pass `include_content=True`.
- **Pass `PRIVATE_HOST_PATTERNS` to Logfire `ScrubbingOptions`.** Define `PRIVATE_HOST_PATTERNS` in `src/devops_cli/security/sanitizer.py` beside `_SECRET_PATTERNS`. The patterns match private domain suffixes (`.internal`, `.local`, `.lan`, `.corp`, `.home.arpa`) and RFC 1918 / loopback IP addresses.
- **Gate `llm.prompt_preview` and `llm.response_preview` in `src/devops_cli/ai/client/unified.py`.** When `get_tracer().capture_llm_content` is false, omit these preview attributes from `ai.llm.dispatch` spans.
- **Pass `capture_llm_content` into `OTelTelemetryClient`.** `get_tracer()` resolves `capture_llm_content` from `TelemetryConfig`.

## Risks / Trade-offs

- [Overly broad host patterns scrub code identifiers] -> Patterns target specific private suffixes (`.internal`, `.local`, `.lan`, `.corp`, `.home.arpa`) and dotted numeric IP octets with word boundaries, avoiding general dotted names.

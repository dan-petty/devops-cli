## ADDED Requirements

### Requirement: First content event deadline on stalled gateway streams
`GatewayCallModel` SHALL set `ModelSettings["first_event_timeout"]` from `ai.first_token_timeout_seconds` (default `60` s) on streamed gateway calls without applying it at the outer whole-call deadline wrapper, closing stalled sends at the deadline. `model_call_error` SHALL report `timed_out=True` for `ModelRequestTimeout`.

#### Scenario: Stalled keep-alive stream times out before second keep-alive and exhausts retries
- **WHEN** a fake gateway emits SSE `: ping` keep-alive comments every `0.4` s with no content event and `GatewayCallModel` uses `first_token_timeout=0.2` and `max_retries=0`
- **THEN** the run raises `ModelRequestTimeout` with `setting == "first_event_timeout"` before a second keep-alive arrives, and `model_call_error` reports `timed_out is True`

### Requirement: Bounded resend on first-event timeout only before the first content event
`failed_before_first_event` SHALL return `True` for `ModelRequestTimeout` only when `error.setting == "first_event_timeout"`, resending stalled attempts up to `ai.max_retries` times. Pauses after the first content event SHALL NOT trigger `first_event_timeout`.

#### Scenario: Stalled first attempt resends once and slow tokens after the first token succeed
- **WHEN** `ai.max_retries` is `1`, a stalled keep-alive send retries against a valid second reply, and another run emits content then pauses longer than `first_token_timeout`
- **THEN** the stalled run retries once (`2` gateway calls) and closes the first stream, while the slow post-first-token stream completes in `1` call

### Requirement: First-token deadline validates below request_timeout_seconds and updates generated docs
`AIConfig` SHALL define `first_token_timeout_seconds` (`ge=1`, default `60`), SHALL reject `first_token_timeout_seconds >= request_timeout_seconds` naming both settings, and generated settings docs (`docs/CONFIGURATION.md`, `docs/ENV_VARS.md`) SHALL list `ai.first_token_timeout_seconds`.

#### Scenario: Invalid timeout nesting and default value
- **WHEN** `Settings()` loads with defaults and `AIConfig` is validated with `first_token_timeout_seconds=120` and `request_timeout_seconds=90`
- **THEN** the default is `60` and validation raises an error naming `ai.first_token_timeout_seconds` and `ai.request_timeout_seconds`

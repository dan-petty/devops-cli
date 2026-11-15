# Proposal

## Why

`SystemOneModel` made one attempt for each request, so a 429 or a 529 failed the caller: the decision point failed open, intake fell to triage and ask-jev stopped with an error. TypeSafe asks for exponential backoff (#5286).

## What Changes

- Add `jev_retry_transport` in `src/devops_cli/ai/providers/__init__.py`: it wraps the client of the Jev provider in `AsyncHTTPX2TenacityTransport`.
- Retry only a 429 and a 529, with `wait_retry_after` over an exponential fallback, at most `CONST_AI_JEV_RETRY_ATTEMPTS` (3) attempts, and a warning for each retry.
- Add `tests/ai/test_jev_retry.py`: a 429 and then a 200, a 529 and then a 200, a 400 with one attempt, and three 429 answers that stop after three.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-ask-jev`: a 429 or a 529 is retried with backoff.

## Impact

- Code: `src/devops_cli/ai/providers/__init__.py`, `src/devops_cli/config/constants.py`
- Tests: `tests/ai/test_jev_retry.py`

## Feasibility

- Read on `origin/main`, 2026-11-15. `pydantic_ai.retries` 2.59.0 holds `AsyncHTTPX2TenacityTransport` and `wait_retry_after`.
- `src/devops_cli/ai/providers/__init__.py:114` builds the provider client and the `system-one` name.
- The caller timeouts stay shorter than the full backoff, so the caller error fires first.
- `uv run pytest tests/ai/test_jev_retry.py` passes with 4 cases.

## Existing Tool Considered

`AsyncHTTPX2TenacityTransport` and tenacity are dependencies. The change wires an existing transport: about 1,000 tokens to build and 50 a quarter to keep.

## Dependencies

None.

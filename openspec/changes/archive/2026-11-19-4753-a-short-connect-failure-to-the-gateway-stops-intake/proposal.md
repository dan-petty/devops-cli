# Proposal: retry gateway connect failures in the AI client

## Why
A short connection failure to the AI gateway can stop a roadmap command like intake.
The existing HTTP transport retry makes five attempts in 38 seconds.
When a temporary network glitch lasts slightly longer, the command fails and writes nothing.
Also, when a connection error occurs, the error message lacks details like the exception class and host.

## What Changes
- Allow up to 10 retry attempts for connect failures in the HTTP transport retry policy.
- Use jittered exponential backoff bounded by the outer read timeout deadline.
- Retry replies that reset before the first stream chunk arrives.
- Prohibit replay if a stream has already yielded output chunks.
- Include the error class, root cause, and backend host in AI client connection errors.
- Ensure only one retry layer handles connection errors without double retries.

## Capabilities
- Roadmap commands ride out temporary connect failures to the model gateway.
- Connection error messages clearly show the failure cause and target host.

## Impact
- Prevents aborted roadmap runs from transient connection drops.
- Does not change CLI command syntax or require spec deltas; sets `skip_specs: true`.

## Feasibility
- Tenacity and HTTPX2 transports already provide the retry primitives.
- Existing unit tests in `tests/ai/client/test_ai_client_retries.py` verify retry behavior.

## Existing Tool Considered
- Tenacity is already in use across the repository.
- Built-in tenacity wait strategies and predicates avoid writing custom retry loops.

# Proposal: #5096

## Why

The Claude client puts `temperature` and `top_p` in `extra_body`. Anthropic SDK 2 sends API
version `2026-10-21`, which refuses those fields, and `top_k`, with HTTP 400. The tests mock the
SDK, so they do not see the request body, and the pinned SDK 1.17.0 hides the failure until
Renovate moves the pin. Closes #5096.

## What Changes

- The Claude request builder checks the installed Anthropic SDK major version. SDK 2 or later
  omits `temperature`, `top_p` and `top_k`; SDK 1 keeps the current behavior.
- An HTTP-seam test forces SDK 2, returns HTTP 400 when a refused field is present, and asserts
  that the call succeeds with none of them.

## Capabilities

### Modified

- `ai-model-sampling`: the Claude sampling gate also depends on the installed SDK's API version.

## Impact

A Claude call on Anthropic SDK 2 no longer fails with HTTP 400. A process on SDK 1.17.0 sends
the same sampling parameters as before.

## Feasibility

Confirmed against the issue and the code: `_build_anthropic_kwargs` in
`src/devops_cli/ai/client/claude.py` builds the sampling gate, and the installed SDK is 1.17.0
while 2.8.0 is the newest. `importlib.metadata.version("anthropic")` reads the installed major.
The HTTP seam test uses the existing `serve_llm` fake.

## Existing Tool Considered

No open tool or library covers the need. The Anthropic SDK owns the API version, and the gateway
and pydantic-ai sit above the Messages call, so none strips the client's `extra_body`. The fix
stays in `claude.py` and its test, with no dependency change.

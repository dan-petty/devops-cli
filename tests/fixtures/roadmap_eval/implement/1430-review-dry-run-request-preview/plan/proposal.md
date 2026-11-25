# Proposal: Review Dry Run Model Request Preview via Client-Built Transport

## Why

Issue #1430. Review dry run previously hand-coded provider request payloads in `_llm_request_preview`, which drifted from actual model requests (omitting sampling, thinking parameters, and token limits, while mishandling base URLs). Furthermore, dry runs could trigger external token lookups (`gh auth token`) and lack proper session bus environment isolation in subprocesses.

## What Changes

- Implement `_llm_request_preview` in `src/devops_cli/ai/review/runner.py` by dispatching the model client's real chat execution against an in-memory `httpx2.MockTransport` recording transport that sends no network traffic.
- Enable `LLMClient` to accept an explicit `transport` or `http_client` via #1001's client factory (`get_llm_client`).
- Ensure preview dictionaries contain the exact recorded method, URL/endpoint, request body/JSON, and headers with authentication secrets sanitized via `mask_secrets`.
- Report missing configuration when Ollama URLs are unset instead of falling back to localhost.
- Ensure `_apply_github_token` in `src/devops_cli/core/process.py` short-circuits during dry runs, preventing child processes from invoking `gh auth token`.
- Preserve `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS` in sanitized subprocess environments (`DEFAULT_ALLOWED_ENV_VARS`) to maintain test floor session bus isolation.
- This change alters no consumer CLI options or external interfaces; it sets `skip_specs: true`.

This change fits one pull request.

## Feasibility

The premise was verified against the codebase:
- `httpx2.MockTransport` is already the project's standard HTTP edge isolation mechanism.
- Testing with `httpx2.MockTransport` confirms that `LLMClient.chat()` formats valid provider requests for `ollama`, `claude`, `openai`, `copilot`, and `gateway` without opening sockets.
- `_apply_github_token` in `src/devops_cli/core/process.py` executes `gh auth token` when running git commands unless guarded by `is_dry_run()`.

## Existing Tool Considered

The change utilizes `httpx2.MockTransport` directly rather than maintaining separate hand-written request formatters per provider. Using the provider SDKs and `LLMClient` against an in-memory transport ensures zero drift between actual client calls and dry-run previews.

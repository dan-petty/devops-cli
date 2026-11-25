## Problem
Checked at release/v0.2.29 (05e9388). `--dry-run` must send nothing and return the requests a real run would send (#412). The review's preview, `_llm_request_preview` (`ai/review/runner.py:165-226`), is a separate hand-written copy of each provider's request, and it no longer matches what the client sends:

- **claude:** `getattr(config, "api_base_url", "https://api.anthropic.com")` returns `None`, because the field exists and is unset, so the previewed endpoint is `None/v1/messages` (`:187-189`).
- **gateway:** the provider falls into the OpenAI branch with an empty base, so the previewed endpoint is `/chat/completions` (`:206-213`).
- **openai:** the preview shows `https://api.openai.com/v1/chat/completions`, while the client posts without `/v1` (the OpenAI base-URL item filed from the same audit).
- **ollama:** the preview falls back to a localhost Ollama URL when none is configured (`:150`, `:171`), which #1165 forbids.
- **all providers:** the previewed body omits `max_tokens`, thinking, sampling and Ollama `options`, which the client sends.

## Proposed remedy
- Build the preview by running the client's own request path against a recording transport: an httpx2 `MockTransport` that records the request and sends nothing. The preview is then the request. Authorization and API-key headers are masked with `mask_secrets`.
- Delete the per-provider branches of `_llm_request_preview` and the localhost fallback in `_resolve_ollama_urls`.
- The recording transport is installed through #1314's hook or #1001's client factory, whichever lands first.

## Acceptance criteria
- [ ] For providers `ollama`, `claude`, `openai`, `copilot` and `gateway`, with base URLs under `https://example.com`, the dry-run preview equals the request a real call records through the HTTP edge fake: method, URL and body, with credentials masked. The `claude` and `gateway` rows fail on the current code.
- [ ] The dry run opens no socket; #1310's floor fails the test otherwise.
- [ ] With no Ollama URL configured, the dry run reports the missing setting instead of previewing a localhost URL.
- [ ] Tests run offline, with fakes only at the HTTP edge (an httpx2 `MockTransport`, through `tests/llm_stream_fakes.route_client` or #1314's fixture) or the process edge. No test patches a devops_cli name.
- [ ] Each new or changed test runs in under 1 s.
- [ ] `uv run devops ci` passes.

Related: #412, #886, #1001, #1314, #1165

Found by the 2026-10-08 client-library audit.

Opened as a borrow (#1153, `budget/borrowed`): the agent filing quota is spent for this cycle, and this is a defect or security finding of the owner-requested 2026-10-08 client-library audit.

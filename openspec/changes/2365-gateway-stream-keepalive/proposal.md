# Proposal

## Why

Issue #2365: a chat call from a workstation to the LLM gateway fails when the model works for more than 125 s before its reply is complete.

- A workstation reaches the gateway through the Cloudflare Tunnel. The Proxy Read Timeout of Cloudflare is 125 s, and only an Enterprise zone can change it.
- The client sends each OpenAI-compatible chat call without streaming (`_openai_compat_messages`), so no byte comes back until the full reply is ready. At 125 s the edge returns 524 and closes the request. LiteLLM counts a 499, and `cancel_on_disconnect` stops the Ollama task.
- The retry transport retries the 524, so each retry runs the same prompt again and the edge stops it again at 125 s.
- On 2026-10-27 the gateway counted 73 such 499s in 24 h, all on `/v1/chat/completions` for `qwen3.8:27b`, the default model. `devops roadmap intake` is one of the callers: its `analysis` calls of about 4,000 prompt tokens reason for long enough to go past 125 s.

## What Changes

- The gateway config sets `litellm_settings.sse_keepalive_ping_interval_seconds: 30`. When a streamed chat call has no data for 30 s, LiteLLM opens the response and writes `: ping` SSE comments until data comes. It does this before the first token too.
- Every OpenAI-compatible chat call that returns one reply (`chat`, `chat_messages`, `chat_structured`) sends `stream: true` with `stream_options.include_usage`. The client builds the reply from the chunks with the accumulator of the OpenAI SDK, `ChatCompletionStreamState`. The reply has the same fields as before: content, reasoning, token usage, finish reason, model, serving backend and deployment model.
- The response size limit applies to the decoded data of the stream. A stream that ends before its final frame fails as the streamed path fails now.
- A failure after the status line comes as an error frame. The client gives it the same error as an HTTP reply with that status, and records it in the spend ledger as a failed attempt.
- The read timeout of a request (`ai.timeout`, `ai.tasks.<task>.timeout`) now limits each wait for the next data of a reply. The gateway's deployment timeouts limit a backend that sends no token. The setting description, `docs/CONFIGURATION.md`, `k8s/README.md` and the comments of the gateway config say so.
- The blocking read of a chat reply (`with_streaming_response` and `_read_limited_body` in `_openai_compat_messages`) is deleted.
- The client and the gateway config change behavior that a consumer sees, so the change carries a spec delta: the new capability `ai-chat-reply-stream`, and an ADDED requirement in `ai-spend-pricing`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `ai-chat-reply-stream`: how an OpenAI-compatible chat call reads its reply as a stream that the gateway keeps open, and how a failure in the stream is reported.

### Modified Capabilities

- `ai-spend-pricing`: a chat call that fails after its status line is recorded as a failed attempt.

## Impact

- `k8s/llm/gateway/config.yaml`, `k8s/README.md`.
- `src/devops_cli/ai/client/openai.py`, `src/devops_cli/ai/spend/transport.py`, `src/devops_cli/config/settings.py`, and the canned chat reply of a review dry run in `src/devops_cli/ai/review/runner.py`.
- `tests/llm_stream_fakes.py`, whose fakes stream a canned chat completion to a request with `stream: true`, as a server does; the tests that build their own transport; `tests/test_ai_chat_reply_stream.py` and `tests/invariants/test_k8s_manifests.py`.
- `docs/CONFIGURATION.md`, which `devops docs generate --sync-readme` rewrites.

## Feasibility

- Cloudflare documents the Proxy Read Timeout as 125 s with status 524, changeable only on Enterprise zones (developers.cloudflare.com, "Connection limits" and "Error 524"). Measured on 2026-10-27: cancelled Ollama tasks ran 124.7 to 125.0 s, and the spend ledger of a workstation had 7 `analysis` calls that failed after 125.1 to 125.8 s.
- A streamed `qwen3.8:27b` reply through the tunnel ran 200 s with no gap longer than 1.7 s, and the probe closed it. Bytes on the wire stop the edge timeout, and no hop (Cloudflare, cloudflared, Traefik) buffers the stream.
- LiteLLM `v1.103.0`, the deployed image, has `sse_keepalive_ping_interval_seconds` (`litellm/__init__.py`). `open_sse_before_first_byte` (`litellm/proxy/common_request_processing.py`) writes `: ping` comments while the upstream call is still open, only for a request with `stream: true`. A failure after a ping is written as `data: {"error": {..., "code": "<status>"}}` and `data: [DONE]` (`sse_error_payload`), the same body as a non-streaming error reply.
- openai 3.26.1 skips SSE comment lines (`openai/_streaming.py`) and raises `openai.APIError` with `code` set to the status for a frame that holds `error`. A probe of `ChatCompletionStreamState` over two pings, reasoning chunks, content chunks and a usage chunk returned the content, the joined `reasoning_content`, the model, the finish reason and the usage with its reasoning tokens.

## Existing Tool Considered

The change uses two open tools and builds none: the keepalive of LiteLLM, and `ChatCompletionStreamState` of the OpenAI SDK to join the chunks. The change deletes the blocking read of a chat reply in `_openai_compat_messages`.

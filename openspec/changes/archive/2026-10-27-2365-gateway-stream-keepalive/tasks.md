# Tasks

## 1. The gateway keeps a streamed chat reply open

- [x] Add a failing invariant test: the gateway config sets `sse_keepalive_ping_interval_seconds` to more than 0 and less than 125
  - Verification: `uv run devops ci test tests/invariants/test_k8s_manifests.py`
- [x] Set `litellm_settings.sse_keepalive_ping_interval_seconds: 30` in the gateway config, and change the comments that relied on the client's 1,200 s timeout
  - Verification: `uv run devops ci test tests/invariants/test_k8s_manifests.py tests/test_llm_pool_metrics.py`
- [x] Describe the keepalive and the timeouts in `k8s/README.md`
  - Verification: `uv run devops ci docs`

## 2. An OpenAI-compatible chat call reads its reply as a stream

- [x] Add failing tests: a reply with pings, reasoning, content and usage chunks; an error frame with code 500 and with code 401; a stream past the size limit; a cut stream and a stream with no chunk; the ledger row of a failure in the stream; the ledger rows of failed attempts whose error body names usage and a model, is HTML, or is cut by the network
  - Verification: `uv run devops ci test tests/test_ai_chat_reply_stream.py tests/test_ai_spend_dispatch.py`
- [x] Send `stream: true` from `_openai_compat_messages`, join the chunks with `ChatCompletionStreamState`, share the frame watcher with the streamed path, map an error frame by its status, and record a failure in the stream with `record_failed_attempt`
  - Verification: `uv run devops ci test tests/test_ai_chat_reply_stream.py tests/test_ai_spend_dispatch.py`
- [x] Delete the blocking read of a chat reply, and answer the chat calls of the existing tests and the canned chat reply of a review dry run with SSE frames
  - Verification: `uv run devops ci test tests/`
- [x] Describe the read timeout as the wait for the next data of a reply, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2365-gateway-stream-keepalive`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

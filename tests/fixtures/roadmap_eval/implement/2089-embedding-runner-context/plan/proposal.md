# Proposal

## Why

Issue #2089: The embedding runner on `ollama-48gib-slow` loaded with context 32768, not the 8192 that the gateway sends.

Investigation of the live cluster and codebase revealed two factors:
1. `ollama-48gib-slow` sets `OLLAMA_CONTEXT_LENGTH: "128000"` and `OLLAMA_KEEP_ALIVE: "-1"`. Before pull request #1987 added `num_ctx: 8192` to the gateway configuration for this tier, the gateway loaded `qwen3-embedding:0.6b` on 2026-10-23 without `num_ctx`. Because `OLLAMA_KEEP_ALIVE: "-1"` keeps runners resident indefinitely, Ollama's `useLoadedRunner` cached that runner at 32768 tokens and reused it across subsequent gateway requests.
2. In `src/devops_cli/ai/rag/embeddings.py`, direct Ollama embedding callers (`_probe_ollama_embed_dimension` and `_query_ollama_node_batch`) sent requests to `/api/embed` without `options: {"num_ctx": ...}`. Any direct invocation or dimension probe against an Ollama daemon without a running instance causes Ollama to load the runner with the model's full default context length (32768).

## What Changes

- Update `EmbeddingsEngine._probe_ollama_embed_dimension` and `_query_ollama_node_batch` in `src/devops_cli/ai/rag/embeddings.py` to send `options={"num_ctx": num_ctx}` with each request to the Ollama `/api/embed` endpoint. The context window is resolved from `self.ai_config.num_ctx` or defaults to `CONST_RAG_MAX_CHUNK_TOKENS` (8192).
- Add regression tests in `tests/test_rag_embeddings.py` verifying that direct Ollama embedding requests and dimension probes pass `options={"num_ctx": 8192}` (or the configured `num_ctx`).
- This change alters internal HTTP payload options for direct Ollama embedding requests and changes no CLI command, option, message, or manifest. The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/rag/embeddings.py`: pass `options: {"num_ctx": ...}` in Ollama embedding payloads.
- `tests/test_rag_embeddings.py`: unit test coverage for Ollama request payloads.

## Feasibility

- Live cluster verification on `ollama-48gib-slow`:
  - Inspected the runner on `ollama-48gib-slow`: `qwen3-embedding:0.6b` was resident since 2026-10-23 (PID 1318) with context 32768 (5.2 GB VRAM).
  - Evicted stale PID 1318 via `keep_alive=0`.
  - Triggered embedding health check from `llm-gateway`: Ollama reloaded `qwen3-embedding:0.6b` with context 8192, occupying 2.8 GB VRAM.
  - Verified `ollama ps` on `ollama-48gib-slow` confirms `CONTEXT: 8192` and `SIZE: 2.8 GB` with `UNTIL: Forever`.
- Direct call verification on Ollama:
  - Direct `POST /api/embed` without options loads `qwen3-embedding:0.6b` with context 32768.
  - Direct `POST /api/embed` with `"options": {"num_ctx": 8192}` loads the model with context 8192.
- Prewarm inspection:
  - `devops ai prewarm` uses `/api/generate`, which Ollama rejects for embedding-only models (`"qwen3-embedding:0.6b" does not support generate`). Prewarm does not load the runner.

## Existing Tool Considered

Direct Ollama `/api/embed` payload options support `options: {"num_ctx": ...}` natively. The change adds `options` to existing HTTP requests within `EmbeddingsEngine`.

# Design

## Context

See proposal.md.
`EmbeddingsEngine` sends embedding requests either through an OpenAI-compatible gateway / API or directly to Ollama nodes.
When sending direct requests to Ollama nodes via `/api/embed`, `EmbeddingsEngine` previously only sent `{"model": self.model, "input": batch_texts}`.
Without `options: {"num_ctx": ...}`, Ollama allocates context up to the daemon or model limit (32768 on slow tier with `OLLAMA_CONTEXT_LENGTH: "128000"`).

## Goals / Non-Goals

**Goals:**
- Ensure all direct Ollama `/api/embed` requests from `EmbeddingsEngine` pass `"options": {"num_ctx": num_ctx}`.
- Resolve `num_ctx` from `self.ai_config.num_ctx` when configured, or default to `CONST_RAG_MAX_CHUNK_TOKENS` (8192).
- Add unit tests verifying `_probe_ollama_embed_dimension` and `_query_ollama_node_batch` include `options={"num_ctx": ...}` in JSON payloads.

**Non-Goals:**
- Modify keep-alive configurations or gateway deployment manifests (the gateway already sends `num_ctx: 8192` as configured in `k8s/llm/gateway/config.yaml`).
- Change embedding chunking logic.

## Decisions

### Decision: Centralize Ollama embed payload construction helper

In `EmbeddingsEngine`:
Resolve context window via property:
```python
@property
def _num_ctx(self) -> int:
    return self.ai_config.num_ctx or CONST_RAG_MAX_CHUNK_TOKENS


def _ollama_embed_payload(self, texts: Sequence[str]) -> dict[str, Any]:
    return {
        "model": self.model,
        "input": list(texts),
        "options": {"num_ctx": self._num_ctx},
    }
```
Both `_probe_ollama_embed_dimension` and `_query_ollama_node_batch` call `_ollama_embed_payload`.

### Decision: Test with request payload inspection

In `tests/test_rag_embeddings.py`, mock httpx client calls and verify the JSON payload received by `post(endpoint, json=...)` contains `"options": {"num_ctx": 8192}`.

## Risks / Trade-offs

- None identified; Ollama's `/api/embed` endpoint standardly accepts `"options": {"num_ctx": ...}`.

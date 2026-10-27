# Tasks

## 1. Test-first implementation

- [x] 1.1 Add failing unit tests in `tests/test_rag_embeddings.py` asserting that direct Ollama requests pass `options: {"num_ctx": ...}`
- [x] 1.2 Update `src/devops_cli/ai/rag/embeddings.py` to send `options={"num_ctx": num_ctx}` in `_probe_ollama_embed_dimension` and `_query_ollama_node_batch`
- [x] 1.3 Verify tests pass and run static checks (`uv run devops ci test tests/test_rag_embeddings.py`)

## 2. Validation and PR

- [x] 2.1 Run fast static checks and OpenSpec validation (`uv run devops openspec check`)
- [x] 2.2 Archive OpenSpec change (`uv run devops openspec archive 2089-embedding-runner-context`)
- [x] 2.3 Create draft pull request (`uv run devops pr create`)
- [x] 2.4 Monitor CI checks and mark PR ready (`uv run devops pr monitor`, `uv run devops pr ready`)

# Tasks

## 1. The disk tier of the embedding cache

Kind: behavior. Reads: `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/ai/spend/ledger.py`. Changes: `src/devops_cli/ai/rag/embedding_disk_cache.py` (new), `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/telemetry/instruments.py`, `tests/ai/rag/test_embedding_disk_cache.py` (new), `tests/ai/rag/test_embedding_cache.py`.

- [x] 1.1 Write failing tests: a second run reads its vectors from disk, only changed texts and another model miss, a corrupt entry and a file that is not a database go to the model, a vector idle for 30 days is removed, Valkey answers before the disk, a disk hit counts as tier `disk`, and the memory cache holds 1,800 vectors
  - Verification: `$ uv run devops ci test tests/ai/rag/test_embedding_disk_cache.py tests/ai/rag/test_embedding_cache.py` fails on the base
- [x] 1.2 Add `EmbeddingDiskCache` over the stdlib `sqlite3`, give `EmbeddingsEngine` the optional `disk_cache` after the Valkey tier, count the tier `disk`, and raise `DEFAULT_RAG_EMBEDDING_CACHE_SIZE` to 2,048
  - Verification: `$ uv run devops ci test tests/ai/rag/test_embedding_disk_cache.py tests/ai/rag/test_embedding_cache.py`

## 2. Intake keeps its embeddings between runs

Kind: behavior. Reads: `src/devops_cli/roadmap/intake/intake.py`. Changes: `src/devops_cli/roadmap/intake/intake_model.py`, `tests/roadmap/intake/test_roadmap_intake_shortlist.py`.

- [x] 2.1 Write a failing test: a second intake run, with its own embedder and a Valkey that refuses each connection, sends no embedding request
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_shortlist.py` fails on the base
- [x] 2.2 Give the embedder of `GatewayIntakeModel` the disk cache under the data directory
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_shortlist.py`

## 3. Documents

Kind: other. Changes: `docs/roadmap/intake.md`, `docs/TELEMETRY.md`.

- [x] 3.1 Describe the disk cache in `docs/roadmap/intake.md`, and the tier `disk` in `docs/TELEMETRY.md` and in the description of the lookup counter
  - Verification: `$ uv run devops ci docs`

## 4. The disk cache key and the vector length (review of #4546)

Kind: behavior. Changes: `src/devops_cli/ai/rag/embedding_disk_cache.py`, `src/devops_cli/ai/rag/embeddings.py`, `tests/ai/rag/test_embedding_disk_cache.py`.

- [x] 4.1 Write failing tests: a stored valid vector of another length goes to the model, a vector of a direct OpenAI request is a miss at the gateway, and vectors of a new length remove the rows of the old length
  - Verification: `$ uv run devops ci test tests/ai/rag/test_embedding_disk_cache.py` fails before the fix
- [x] 4.2 Key the rows by the provider and the model name that the request sends, record one vector length for each key, and treat a row of another length as a miss
  - Verification: `$ uv run devops ci test tests/ai/rag/test_embedding_disk_cache.py`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

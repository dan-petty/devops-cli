# Proposal: #4447

## Why

Issue #4447: each `devops roadmap intake` run on a workstation sends all texts of its comparison set to the embedding model again. On 2026-11-11, one `--plan` call on `origin/main` 7234d718 embedded 1,866 texts in 59 gateway requests in 155 s, with 0 memory hits, 0 Valkey hits and 1,866 misses. The Valkey tier of `EmbeddingsEngine` has no server at the default `valkey.url` on a workstation, and the memory tier of a new process is empty. The memory tier also holds only 1,024 vectors, fewer than one comparison set.

## What Changes

- A new disk tier of the embedding cache, `EmbeddingDiskCache` (`src/devops_cli/ai/rag/embedding_disk_cache.py`), keeps vectors in the SQLite file `ai/embeddings.db` under the data directory, with the stdlib `sqlite3`. The key of a row is the embedding model and the SHA-256 of the text that the model gets.
- `EmbeddingsEngine` takes an optional `disk_cache`. It looks up a text in the memory tier, then in Valkey, then on disk, and sends only the misses to the model. A disk hit goes into the memory tier and into Valkey. A fresh vector goes into all three tiers.
- The embedder of intake (`GatewayIntakeModel`) gives the engine the disk cache. Other callers, such as the RAG indexer and the embedding benchmark, give none, so a benchmark still measures the model and a large index does not fill the file.
- A stored value that is not a vector is a miss, and the fresh vector replaces it. A file that cannot be opened, read or written turns the disk tier off for the run, with one warning that names the file. Each write removes the vectors that no run used for 30 days.
- `DEFAULT_RAG_EMBEDDING_CACHE_SIZE` goes from 1,024 to 2,048 vectors, so one process holds one comparison set.
- `devops_cli_embedding_cache_lookups_total` gets the tier `disk`.
- The change alters what intake sends and what a metric counts, so it carries a delta: the new capability `embedding-disk-cache` and a change of `metric-instruments`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `embedding-disk-cache`: the disk tier of the embedding cache, its key, its fallback to the model and its expiry, the order of the tiers, and the size of the memory tier.

### Modified Capabilities

- `metric-instruments`: the embedding cache lookup counter names the tier `disk`.

## Impact

- `src/devops_cli/ai/rag/embedding_disk_cache.py` (new), `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/roadmap/intake/intake_model.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/telemetry/instruments.py`.
- `docs/roadmap/intake.md`, `docs/TELEMETRY.md`.
- Tests: `tests/ai/rag/test_embedding_disk_cache.py` (new), `tests/ai/rag/test_embedding_cache.py`, `tests/roadmap/intake/test_roadmap_intake_shortlist.py`.
- The Service runs intake too. There, Valkey answers first, and the file is on the data volume of the Service. The change adds no Valkey instance and no package.

## Feasibility

Checked on `origin/main` 7234d718 (2026-11-11), Python 3.14.10 with SQLite 3.53.1:

- `uv run devops valkey ping` in the devcontainer gives `Error 111 connecting to localhost:6379. Connection refused.` So the Valkey tier gives no hit on a workstation.
- One `uv run devops roadmap intake --plan` call, measured with a wrapper of `EmbeddingsEngine` in the same process: 155.1 s in `embed_texts`, 1,866 texts, 59 answered `/v1/embeddings` requests, 0 memory hits, 0 Valkey hits, 1,866 misses, 249 s for the whole call.
- Intake embeds the comparison set and the candidates in one `embed_texts` call (`_Decider._embed` in `src/devops_cli/roadmap/intake/intake.py`), and builds its engine in `GatewayIntakeModel._embedder`. So one tier under the engine serves each intake run.
- The existing keys hash the text after the task prefix of the model, with the model name (`_EmbeddingLRUCache._key`, `EmbeddingsEngine._valkey_key`). The disk key uses the same text and model.
- The owner plans a central Valkey store (#4517), so this change adds no Valkey instance to the devcontainer.

## Existing Tool Considered

- SQLite through the stdlib `sqlite3` module: open, maintained, already in use for the spend ledger (`src/devops_cli/ai/spend/ledger.py`), and with no new package. The change uses it.
- `diskcache` 5.6.3: not in `uv.lock`, last release on 2023-08-31, and it has the advisory GHSA-w8v5-vhqr-4h9v (CVE-2025-69872): it reads pickle by default, so a person with write access to the cache folder can run code. Rejected.
- A Valkey in the devcontainer (the design in the issue): rejected, because #4517 plans one central Valkey store, and a second instance in each container adds a process, a package and a lifecycle task.
- `cachetools` is in `uv.lock`, but it holds entries in memory only.

The tier is about 140 lines of code over `sqlite3`. Cost to build, keep and fix: about 250k tokens and 3 hours of elapsed time. The change deletes no internal code: the memory tier and the Valkey tier stay.

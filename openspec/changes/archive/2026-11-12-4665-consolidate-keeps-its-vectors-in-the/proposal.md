# Proposal: #4665

## Why

Issue #4665: `devops roadmap consolidate` keeps a second local store of embeddings, the file `roadmap/consolidate/embeddings.json` under the data directory (`src/devops_cli/roadmap/consolidate_shortlist.py`, `embed_issues`). The same vectors can be in the tiers of the embedding cache: memory, Valkey and the disk tier `ai/embeddings.db` of #4447 and #4546. The owner rule says: do not add a second store for the same data. The job also builds its engine with no disk tier, so its vectors never reach the shared disk file, and a hit in the file is not counted on `devops_cli_embedding_cache_lookups_total`.

## What Changes

- The embedder of the job (`GatewayEmbedder` in `src/devops_cli/roadmap/consolidate_judge.py`) gives `EmbeddingsEngine` the disk tier `embedding_disk_cache()`, as the embedder of intake does.
- `embed_issues` sends each text once to the embedder and keeps no file. The text stays the same: the title and the text of a person, outside the sections of the refine job and the alternatives job.
- The code that reads and writes `embeddings.json` is removed: `_EmbeddingFile`, `embeddings_path`, `_read_cache`, `_write_cache` and the constant `CONST_ROADMAP_CONSOLIDATE_EMBEDDINGS_FILE`. `consolidation_groups` takes no model name and no data directory. `Edges.embedding_model` and `GatewayEmbedder.model` have no reader left, so they are removed.
- The Valkey key fix stays in #4569.
- The change alters what the job keeps and what a metric counts, so it carries a delta of `roadmap-consolidate-shortlist`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-consolidate-shortlist`: the job keeps its vectors in the shared tiers of the embedding cache and keeps no embedding file of its own.

## Impact

- `src/devops_cli/roadmap/consolidate_shortlist.py`, `src/devops_cli/roadmap/consolidate_judge.py`, `src/devops_cli/roadmap/consolidate.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/config/constants.py`.
- Tests: `tests/commands/test_roadmap_consolidate_cmd.py`, `tests/roadmap/test_roadmap_consolidate_shortlist.py`, `tests/roadmap/test_roadmap_consolidate.py`, `tests/roadmap/test_roadmap_consolidate_judge.py`.
- An existing `embeddings.json` stays on disk and no code reads it. A person can delete it. The first run after the change embeds the open items once, unless Valkey or the disk tier holds them already.
- No new package and no new Valkey instance.

## Feasibility

Checked on `origin/main` 21b116ea (2026-11-12):

- `git grep -n -E 'embeddings\.json|CONSOLIDATE_EMBEDDINGS_FILE'` finds the store in `consolidate_shortlist.py` (`embeddings_path`, `_read_cache`, `_write_cache`) and the constant in `constants.py`. The other hits are an archived proposal and a test filter.
- `GatewayEmbedder._built` calls `create_embedder(self._ai, api_key=self._api_key)` with no `disk_cache`. `GatewayIntakeModel._embedder` passes `disk_cache=embedding_disk_cache()`. `EmbeddingsEngine` looks up memory, then Valkey, then disk, and counts each text on `devops_cli_embedding_cache_lookups_total` with its tier.
- The local data directory of the main checkout holds both stores: `roadmap/consolidate/embeddings.json` with 312 vectors of `qwen3-embedding:0.6b` (4,315,611 bytes), and `ai/embeddings.db` with 4,191 rows (2,324 of `gateway/qwen3-embedding:0.6b` and 1,867 of `qwen3-embedding:0.6b`).
- A test through the command with the real engine, the HTTP fake and the OTLP fake fails on the base: the second run counts no cache lookup, because the file answers before the engine; and the folder of the job holds `embeddings.json` beside the plan.

## Existing Tool Considered

The `EmbeddingsEngine` seam with the disk tier of #4447 and #4546, and the shared Valkey tier. No new tool. The issue estimates about 40,000 tokens and 1 hour to build.

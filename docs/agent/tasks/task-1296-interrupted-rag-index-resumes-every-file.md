# Task: An Interrupted RAG Index Resumes Every File Whose Chunks Were Not All Stored (#1296)

**Issue**: [#1296](https://github.com/dan-petty/devops-cli/issues/1296)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: scope/ai

## Description
#1065 made a failed embedding batch end `devops ai rag index` with exit 1 and advertised a fast resume without `--force`. `_update_incremental_cache` cached every file with a chunk in the batch just stored. A file whose chunks spanned a later, failed batch was therefore cached under its current hash, and the resume skipped it, so its remaining chunks were never stored while the run reported success.

The v0.2.28 notes also said semantic chunks are bounded "to at most 8,192 tokens". The chunker measures that bound with the project's four-characters-per-token estimate, so the notes now say 8,192 estimated tokens. Measuring the cap with a real tokenizer is a separate follow-up item.

## Key Changes
- **Cache a file only once all of its chunks are stored** (`src/devops_cli/ai/rag/indexer.py`):
  - `index_workspace` counts each file's pending chunks across both collections (`collections.Counter`) and passes the count to both `_upsert_chunks` calls.
  - `_update_incremental_cache` decrements a file's count for each stored chunk and caches the file only when the count reaches zero.
  - No purge change: a partly stored file has no cache entry under its current hash, so the resume embeds it again, and its deterministic chunk ids overwrite the points already stored.
- **Test** (`tests/test_rag_indexer_retriever.py`): `test_failed_batch_inside_a_file_leaves_that_file_for_resume` indexes a multi-chunk file with one chunk per batch, fails the second batch, and resumes with a healthy embedder. The file is uncached after the failure and every chunk id is stored after the resume. At 61f9b67 the file was cached and three of its chunk ids were missing.
- **Changelog** (`changelog.d/1296.md`): records the resume fix and states the cap as 8,192 estimated tokens.

## Acceptance Criteria
- [x] A file is cached only once all of its chunks are stored, so a resume without `--force` stores every chunk of a file that spanned the failed batch; re-upserting is idempotent because chunk ids are deterministic (`src/devops_cli/ai/rag/indexer.py`).
- [x] A test that fails at 61f9b67 covers the resume (`tests/test_rag_indexer_retriever.py`).
- [x] `changelog.d/1296.md` records the change and states the cap as 8,192 estimated tokens; `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] `uv run devops ci` passes.
- Release process: before #1283 merges, the v0.2.28 section of `CHANGELOG.md` takes this fragment in place of the #1065 wording "bound semantic chunks to at most 8,192 tokens" and "retaining earlier indexed batches in cache for fast incremental resume", through a `chore/open-v0.2.28-<slug>` pull request.

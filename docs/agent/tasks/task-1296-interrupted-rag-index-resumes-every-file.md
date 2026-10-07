# Task: An Interrupted RAG Index Resumes Every File Whose Chunks Were Not All Stored (#1296)

**Issue**: [#1296](https://github.com/dan-petty/devops-cli/issues/1296)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: scope/ai

## Description
#1065 made a failed embedding batch end `devops ai rag index` with exit 1 and advertised a fast resume without `--force`. `_update_incremental_cache` cached every file with a chunk in the batch just stored. A file whose chunks spanned a later, failed batch was therefore cached under its current hash, and the resume skipped it, so its remaining chunks were never stored while the run reported success.

The v0.2.28 notes also said semantic chunks are bounded "to at most 8,192 tokens". The chunker measures that bound with the project's four-characters-per-token estimate, so the notes now say 8,192 estimated tokens. Measuring the cap with a real tokenizer is follow-up #1300.

## Key Changes
- **Cache a file only once all of its chunks are stored** (`src/devops_cli/ai/rag/indexer.py`):
  - `index_workspace` counts each file's pending chunks across both collections (`collections.Counter`) and passes the count to both `_upsert_chunks` calls.
  - `_update_incremental_cache` decrements a file's count for each stored chunk. When the count reaches zero, it caches the file under its content hash. Until then it caches the file as `CONST_RAG_INCOMPLETE_FILE_MARKER`, a value no content hash matches.
  - The resume therefore embeds a partly stored file again, and its deterministic chunk ids overwrite the points already stored.
  - Both purges find files through the cache, so a partly stored file that is deleted or edited before the resume still has its stored points purged. Leaving it out of the cache would have orphaned them.
- **Tests** (`tests/test_rag_indexer_retriever.py`): a multi-chunk file beside a small one is indexed with one chunk per batch, an embedding batch inside the big file fails, and a healthy embedder resumes.
  - `test_failed_batch_inside_a_file_leaves_that_file_for_resume`: the file is cached as incomplete after the failure, and every chunk id is stored after the resume. At 61f9b67 the file was cached under its hash and chunks were missing.
  - `test_a_partly_stored_file_deleted_before_the_resume_leaves_no_points`: only the small file's chunks remain. Leaving the file uncached would have left a chunk orphaned.
  - `test_a_partly_stored_file_edited_before_the_resume_keeps_only_its_new_chunks`: the store holds exactly the edited file's chunks and the small file's.
- **Changelog** (`changelog.d/1296.md`): records the resume fix and states the cap as 8,192 estimated tokens.

## Acceptance Criteria
- [x] A file is cached under its hash only once all of its chunks are stored, and as incomplete until then. A resume without `--force` stores every chunk of a file that spanned the failed batch, and a deleted or edited file's stored chunks are still purged. Re-upserting is idempotent because chunk ids are deterministic (`src/devops_cli/ai/rag/indexer.py`).
- [x] Tests cover the resume and a delete or edit before it; the resume and delete tests fail at 61f9b67 (`tests/test_rag_indexer_retriever.py`).
- [x] `changelog.d/1296.md` records the change and states the cap as 8,192 estimated tokens; `CHANGELOG.md` and `docs/ROADMAP.md` are not edited.
- [x] `uv run devops ci` passes.
- Release process: before #1283 merges, the v0.2.28 section of `CHANGELOG.md` takes this fragment in place of the #1065 wording "bound semantic chunks to at most 8,192 tokens" and "retaining earlier indexed batches in cache for fast incremental resume", through a `chore/open-v0.2.28-<slug>` pull request.

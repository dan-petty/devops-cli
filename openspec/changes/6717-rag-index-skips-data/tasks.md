# Tasks

## 1. The indexer leaves out generated and vendored files

Kind: behavior. Reads: `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/git/operations.py`, `src/devops_cli/roadmap/project_review/git_read.py`. Changes: `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/git/operations.py`, `tests/ai/rag/test_workspace_indexing.py`.
Adds: `paths_with_attributes`

- [x] 1.1 Write the failing tests in `tests/ai/rag/test_workspace_indexing.py` for the three scenarios of the requirement "The indexer leaves out generated and vendored files": `test_indexing_skips_files_that_gitattributes_marks_generated_or_vendored` (a real `git init` in `tmp_path`), `test_one_git_call_reads_the_attributes_of_all_files` (`process_fake` answers `git rev-parse --show-toplevel` and `git check-attr`, and the test reads back one `check-attr` call whose standard input holds the three paths) and `test_a_directory_with_no_repository_starts_no_attribute_read`
  - Verification: `$ uv run devops ci test tests/ai/rag/test_workspace_indexing.py` fails on the base
- [x] 1.2 Add `paths_with_attributes(repo_dir, paths, attributes)` to `src/devops_cli/git/operations.py`: one `git -C <repo_dir> check-attr -z --stdin <attributes>` with the paths on standard input, as a local read, the paths whose value is `set` or `true` for one of the attributes, and `GitOperationError` for a status other than 0. In `WorkspaceIndexer.collect_files`, when `git_show_toplevel` finds a work tree, leave out the files that it gives for `linguist-generated` and `linguist-vendored`
  - Verification: `$ uv run devops ci test tests/ai/rag/test_workspace_indexing.py` passes

## 2. A failed batch is retried, then skipped, and the run exits 1 at the end

Kind: behavior. Reads: `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/http/retry.py`, `tests/support/fakes/embeddings.py`, `tests/support/fakes/clock.py`. Changes: `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/lang/en/errors.py`, `tests/ai/rag/test_indexing_failure_and_resume.py`.
Adds: `is_transient_embedding_error`, `ERRORS.rag.batches_skipped`

- [x] 2.1 In `tests/ai/rag/test_indexing_failure_and_resume.py`, replace `test_a_failed_second_batch_ends_with_exit_1_and_keeps_the_first_batch` with `test_a_batch_that_fails_each_try_is_skipped_and_the_run_exits_1_naming_its_file` (scenarios "One batch fails each try" and "The next run embeds the skipped file", on the `clock` fixture), and add `test_a_batch_that_the_retry_embeds_is_indexed` and `test_a_permanent_failure_ends_the_run_with_no_retry`. Keep the tests of a partly stored file: their failure is transient, so they skip the batch and resume
  - Verification: `$ uv run devops ci test tests/ai/rag/test_indexing_failure_and_resume.py` fails on the base
- [x] 2.2 Rename `_is_transient_embedding_error` to `is_transient_embedding_error` in `src/devops_cli/ai/rag/embeddings.py`. In `WorkspaceIndexer._upsert_chunks`, embed each batch through `tenacity.Retrying` (2 attempts, `retry_if_exception(is_transient_embedding_error)`, `wait_exponential_jitter`, `sleep=clock.sleep`). Skip a batch that fails both attempts: record its files, and mark them `CONST_RAG_INCOMPLETE_FILE_MARKER` in the cache. Raise the `batch_failed` error at once for a permanent error. At the end of `index_workspace`, after the cache and the counts are saved, raise `EmbeddingsError` with `ERRORS.rag.batches_skipped`, exit status 1 and `details` `skipped_files` and `first_error`
  - Verification: `$ uv run devops ci test tests/ai/rag/test_indexing_failure_and_resume.py tests/ai/rag/test_workspace_indexing.py tests/commands/test_ai_rag_commands.py` passes
- [x] 2.3 Regenerate the documentation for the new message
  - Verification: `$ uv run devops docs generate`

## 3. Mark the tiktoken fixtures vendored

Kind: data. Reads: `.gitattributes`. Changes: `.gitattributes`.

- [x] 3.1 Add `tests/fixtures/tiktoken/*.tiktoken linguist-vendored` to `.gitattributes`, with a comment that names them the data of tiktoken
  - Verification: `$ git check-attr linguist-vendored -- tests/fixtures/tiktoken/o200k_base.tiktoken tests/fixtures/tiktoken/cl100k_base.tiktoken`

## 4. State the skips and the failed batches in the knowledge base

Kind: documents. Reads: `src/devops_cli/ai/knowledge_base/devops_cli/tasks/rag_context_indexing.md`. Changes: `src/devops_cli/ai/knowledge_base/devops_cli/tasks/rag_context_indexing.md`.

- [ ] 4.1 In `rag_context_indexing.md`, state that the indexer leaves out the files that `.gitattributes` marks `linguist-generated` or `linguist-vendored`, and that a transient batch failure gets one more attempt, then the run skips the batch, indexes the other batches and exits 1 with the files that it did not index
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the merge, run `devops ai rag index --include-kb` on this repository, and check that `devops ai rag status` shows points in `devops_code` and `devops_docs` (acceptance criterion 2 of #6717).
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

# Tasks

## 1. The indexer leaves out vendored files

Kind: behavior. Reads: `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/git/operations.py`, `src/devops_cli/roadmap/project_review/git_read.py`. Changes: `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/git/operations.py`, `tests/ai/rag/test_workspace_indexing.py`.
Adds: `paths_with_attributes`

- [x] 1.1 Write the failing tests in `tests/ai/rag/test_workspace_indexing.py` for the three scenarios of the requirement "The indexer leaves out vendored files": `test_indexing_skips_vendored_files_and_keeps_generated_ones` (a real `git init` in `tmp_path`, with a `linguist-generated` Markdown file that the index keeps), `test_one_git_call_reads_the_attributes_of_all_files` (`process_fake` answers `git rev-parse --show-toplevel` and `git check-attr`, and the test reads back one `check-attr` call whose standard input holds the three paths) and `test_a_directory_with_no_repository_starts_no_attribute_read`
  - Verification: `$ uv run devops ci test tests/ai/rag/test_workspace_indexing.py` fails on the base
- [x] 1.2 Add `paths_with_attributes(repo_dir, paths, attributes)` to `src/devops_cli/git/operations.py`: one `git -C <repo_dir> check-attr -z --stdin <attributes>` with the paths on standard input, as a local read, the paths whose value is `set` or `true` for one of the attributes, and `GitOperationError` for a status other than 0. In `WorkspaceIndexer.collect_files`, when `git_show_toplevel` finds a work tree, leave out the files that it gives for `linguist-vendored`
  - Verification: `$ uv run devops ci test tests/ai/rag/test_workspace_indexing.py` passes

## 2. A failed batch is retried or skipped by its HTTP status, and the run exits 1 at the end

Kind: behavior. Reads: `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/http/retry.py`, `tests/support/fakes/embeddings.py`, `tests/support/fakes/clock.py`, `litellm/proxy/route_llm_request.py`. Changes: `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/ai/rag/embeddings.py`, `src/devops_cli/lang/en/errors.py`, `tests/ai/rag/test_indexing_failure_and_resume.py`, `tests/ai/rag/test_embedding_provider_failures.py`, `tests/commands/test_ai_rag_commands.py`.
Adds: `is_transient_embedding_error`, `is_input_refused_error`, `EmbeddingsError.status`, `ERRORS.rag.batches_skipped`

- [x] 2.1 In `tests/ai/rag/test_embedding_provider_failures.py`, add `test_a_gateway_error_reply_gives_its_http_status`, `test_a_gateway_that_does_not_answer_gives_no_status` and `test_an_ollama_error_gives_a_status_only_when_each_node_answered_it`. In `tests/ai/rag/test_indexing_failure_and_resume.py`, replace `test_a_failed_second_batch_ends_with_exit_1_and_keeps_the_first_batch` with `test_a_batch_that_fails_each_try_is_skipped_and_the_run_exits_1_naming_its_file` (scenarios "One batch fails each try" and "The next run embeds the skipped file", on the `clock` fixture, for a 504, a 429 and a timeout), and add `test_a_batch_that_the_retry_embeds_is_indexed`, `test_a_batch_whose_input_the_endpoint_refuses_is_skipped_with_no_retry` (400, 413, 422), `test_two_refused_batches_before_an_embedded_batch_end_the_run` and `test_a_permanent_failure_ends_the_run_with_no_retry` (401, 403, 404, no status). The fakes raise `EmbeddingsError` with the status of the reply. Keep the tests of a partly stored file: their failure is transient, so they skip the batch and resume
  - Verification: `$ uv run devops ci test tests/ai/rag/test_embedding_provider_failures.py` fails on the base
  - Verification: `$ uv run devops ci test tests/ai/rag/test_indexing_failure_and_resume.py` fails on the base
- [x] 2.2 Rename `_is_transient_embedding_error` to `is_transient_embedding_error` in `src/devops_cli/ai/rag/embeddings.py`. Add `status` to `EmbeddingsError`: `_reply_vectors` sets it, and `_embedding_error` keeps the status that each endpoint gave. Add `is_input_refused_error` for 400, 413 and 422. In `WorkspaceIndexer._upsert_chunks`, embed each batch through `tenacity.Retrying` (2 attempts, a transient error that is not a refused input, `wait_exponential_jitter`, `sleep=clock.sleep`). Skip a batch that fails both attempts or whose input the endpoint refuses: record its files, and mark them `CONST_RAG_INCOMPLETE_FILE_MARKER` in the cache. Raise the `batch_failed` error at once for any other error, and for a second refused batch while no batch got vectors. At the end of `index_workspace`, after the cache and the counts are saved, raise `EmbeddingsError` with `ERRORS.rag.batches_skipped`, exit status 1 and `details` `skipped_files` and `first_error`
  - Verification: `$ uv run devops ci test tests/ai/rag/test_indexing_failure_and_resume.py tests/ai/rag/test_workspace_indexing.py tests/commands/test_ai_rag_commands.py` passes
- [x] 2.3 Regenerate the documentation for the new message
  - Verification: `$ uv run devops docs generate`

## 3. Mark the tiktoken fixtures vendored

Kind: data. Reads: `.gitattributes`. Changes: `.gitattributes`.

- [x] 3.1 Add `tests/fixtures/tiktoken/*.tiktoken linguist-vendored` to `.gitattributes`, with a comment that names them the data of tiktoken
  - Verification: `$ git check-attr linguist-vendored -- tests/fixtures/tiktoken/o200k_base.tiktoken tests/fixtures/tiktoken/cl100k_base.tiktoken`

## 4. State the skips and the failed batches in the knowledge base

Kind: documents. Reads: `src/devops_cli/ai/knowledge_base/devops_cli/tasks/rag_context_indexing.md`. Changes: `src/devops_cli/ai/knowledge_base/devops_cli/tasks/rag_context_indexing.md`.

- [x] 4.1 In `rag_context_indexing.md`, state that the indexer leaves out the files that `.gitattributes` marks `linguist-vendored` and keeps the `linguist-generated` files, that a transient batch failure gets one more attempt and a refused input none, and that the run then skips the batch, indexes the other batches and exits 1 with the files that it did not index
  - Verification: `$ uv run devops ci docs`

## 5. A run stops when the embedding endpoint is not available

Kind: behavior. Reads: `src/devops_cli/ai/rag/investigator.py`, `src/devops_cli/ai/rag/indexer.py`. Changes: `src/devops_cli/ai/rag/indexer.py`, `src/devops_cli/lang/en/errors.py`, `tests/ai/rag/test_indexing_failure_and_resume.py`, `tests/commands/test_ai_rag_commands.py`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/rag_context_indexing.md`.
Adds: `ERRORS.rag.endpoint_down`

- [x] 5.1 In `tests/ai/rag/test_indexing_failure_and_resume.py`, add `test_a_transient_failure_of_the_first_batch_ends_the_run` (504, 429, timeout), `test_three_batches_in_a_row_that_fail_end_the_run`, `test_a_batch_that_the_endpoint_answers_sets_the_count_of_failed_batches_to_0` (an embedded and a refused batch) and `test_a_skipped_code_batch_does_not_stop_the_docs_collection`. In `tests/commands/test_ai_rag_commands.py`, fail the second file, not the first
  - Verification: `$ uv run devops ci test tests/ai/rag/test_indexing_failure_and_resume.py` fails before 5.2
- [x] 5.2 In `src/devops_cli/ai/rag/indexer.py`, give each run a pybreaker `CircuitBreaker` (`fail_max=_FAILED_BATCHES_IN_A_ROW`, an `exclude` for each error that `_is_retryable` refuses, `throw_new_error_on_trip=False`) around the two attempts of a batch. After a transient skip, when the breaker is open or no batch got vectors, raise `EmbeddingsError` with `ERRORS.rag.endpoint_down`, exit status 1 and `details` `skipped_files` and `last_error`. State the stop in `rag_context_indexing.md`
  - Verification: `$ uv run devops ci test tests/ai/rag/test_indexing_failure_and_resume.py tests/commands/test_ai_rag_commands.py` passes

## Workflow follow-up

- Pending a person: after the merge, run `devops ai rag index --include-kb` on this repository, and check that `devops ai rag status` shows points in `devops_code` and `devops_docs` (acceptance criterion 2 of #6717).
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

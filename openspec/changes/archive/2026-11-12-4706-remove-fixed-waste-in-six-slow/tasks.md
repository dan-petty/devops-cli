# Tasks

## 1. The six tests do only the work that they check (other)

- [x] 1.1 Collect the document references one time in `test_every_hand_written_document_names_only_real_commands` of `tests/docs/test_docs_inventory.py`.
  - Verification: `$ uv run devops ci test tests/docs/test_docs_inventory.py`
- [x] 1.2 Remove the JSON export step from `test_docs_cli_generate_and_check` of `tests/docs/test_docs.py`, and read the `groups` key in the JSON step of `test_docs_cli_dry_run_and_format_helpers`.
  - Verification: `$ uv run devops ci test tests/docs/test_docs.py`
- [x] 1.3 Give the forage dry run its own test in `tests/commands/test_ai_rag_ingest_analyze_dry_run.py`, with a directory of one file as `--repo`.
  - Verification: `$ uv run devops ci test tests/commands/test_ai_rag_ingest_analyze_dry_run.py`
- [x] 1.4 Shut the listener of `malformed_endpoint` in `tests/support/sandbox.py` down before it closes, and fail the teardown when the thread does not end.
  - Verification: `$ uv run devops ci test tests/commands/test_sandbox_metrics.py`
- [x] 1.5 Run the memory test of `tests/server/test_service_memory.py` for 50 rounds, and rename the test and its docstrings. A run with a store of no byte bound fails it.
  - Verification: `$ uv run devops ci test tests/server/test_service_memory.py`
- [x] 1.6 Remove `deadline=800` from `test_chunker_hypothesis_properties` of `tests/ai/rag/test_polyglot_chunking.py`.
  - Verification: `$ uv run devops ci test tests/ai/rag/test_polyglot_chunking.py`

## 2. The spec names the rounds of the test (other)

- [x] 2.1 Change the scenario "The heap after many rounds" of `github-session-answers` to 50 rounds.
  - Verification: `$ uv run devops openspec check`

## Workflow follow-up

- The glob matches of `hand_written_documents` in `src/devops_cli/docs/inventory.py` take a large part of each documented argv check: #4979.

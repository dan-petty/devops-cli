# Proposal

## Why

Issue #4002 is item 3 of the Fit note of #1329. Four test files still test the library tools and the RAG command helper through internals or through a private `CliRunner`. The shared fakes and fixtures of #1307 exist, so the tests can use them now.

The tree at `origin/main` 734e060b holds these facts. They were counted again, because the text of #1329 is older than the tree.

- `tests/ai/rag/test_ai_subcommands_rag.py` imports the private `commands.ai._try_retrieve_rag_context` and patches `load_settings`, `QdrantClient.is_alive` and `SemanticRetriever.retrieve_context`. Its investigator cases are already held by `tests/ai/rag/test_investigation_context.py`. Its `devops --dry-run ai pipeline` case is already held by `tests/commands/test_ai_cmd.py`.
- `tests/ai/analyze/test_library_drift_auditor.py` tests `ai/library/drift_auditor.py` from the wrong folder. It patches `devops_cli.ai.analyze.cache.analysis_directory` twice and `Path.write_text`, builds a private Typer app from `audit_library_usage_cmd`, and keeps a module-level `CliRunner()`.
- `tests/ai/library/test_docs_ingester.py` and `tests/ai/library/test_library_ingest.py` mix domain tests with CLI tests, keep a module-level `CliRunner()` each, invoke the private `ai_app`, and hold three tests that only check that a pydantic model keeps the values it was given.
- The docs ingester tests already use the `web` fake. They stay on its public methods, so item 4 of #1329 (render HTML through the shared converter and markdown-it) can change the internals with no test change.

## What Changes

- Library tests mirror `src/devops_cli/ai/library/`, one file per behavior, in `tests/ai/library/`:
  - `test_docs_ingest_local.py`, `test_docs_ingest_remote.py` (docs ingester);
  - `test_signature_extraction.py`, `test_library_contract_store.py`, `test_package_introspection.py` (introspector);
  - `test_drift_findings.py`, `test_drift_report_saving.py` (drift auditor).
- CLI tests use the `cli` fixture, in `tests/commands/`: `test_ai_ingest_docs.py`, `test_ai_ingest_library.py`, `test_ai_audit_library_usage.py`, and `test_ai_retrieve_rag_context.py` for the public `retrieve_rag_context` of `commands/ai.py`, over the `qdrant`, `embedder` and `config` fixtures.
- `tests/support/library_contracts.py` holds the demo contract and workspace that the drift tests share.
- The report path of the audit command is set through `DEVOPS_CLI_DATA_ANALYSIS_DIR`, as the floor sets the data directory. The disk edge is real: a path under a file, and a read-only report file. No test patches `Path.write_text`.
- Deleted: the four files named above, the two `analysis_directory` patches, the `Path.write_text` patch, the private `_try_retrieve_rag_context` import, the private `ai_app` and `audit_library_usage_cmd` imports, the three `CliRunner()` instances, and three tests that check only a model constructor (`test_doc_chunk_model`, `test_parameter_signature_model`, `test_function_signature_model`). A mutation of a model field is held by the tests that read the fields after a real extraction or ingest.
- This change alters no behavior a consumer observes and touches no path under `src/`. It has no spec delta, and `skip_specs: true` is set.
- This change fits one pull request. Item 4 of #1329 (the docs ingester rewrite) is another issue.

## Impact

- `tests/ai/library/`, `tests/ai/analyze/`, `tests/ai/rag/`, `tests/commands/`, `tests/support/library_contracts.py`.
- No document names the deleted files outside archived changes, which stay as history.

## Feasibility

Checked on `origin/main` 734e060b, 2026-11-07. The premise of #1329 item 3 holds, with the tree changes below.

- The shared seams exist: `uv run pytest tests/commands/test_ai_rag_commands.py tests/ai/rag/test_investigation_context.py` passes on the `qdrant`, `embedder`, `web`, `cli` and `config` fixtures.
- Item 1 (#3850) moved the wiring out of the commands, so `retrieve_rag_context` calls `resolve_rag_components`, and the fakes reach it through their seams with no patch.
- Item 2 (#3862) migrated `tests/ai/rag/`. It left `test_ai_subcommands_rag.py` for this item.
- The two retrieval cases of `test_ai_subcommands_rag.py` test the investigator, and `tests/ai/rag/test_investigation_context.py` holds the same behavior over the fakes. Only the command helper is new ground: the settings switch and the answer of `None` for each failure.
- `DEVOPS_CLI_DATA_ANALYSIS_DIR` decides `data.analysis_dir` in a test, because the floor sets `DEVOPS_CLI_DATA_DIR` and the environment beats the config file (`uv run pytest` shows the report in `<tmp>/.data/analysis` when the `config` fixture sets the key).
- Mutation check, run on the product code and restored: removing the `unlink` in `DriftReport.save`, the `save_error` record, the `UNRECOGNIZED_KWARG` type, the same-origin check of the crawler, the file name or the validation error handling of the contract store, the `enabled` switch of `retrieve_rag_context` and the `save_error` message of the command each fail a migrated test. Two mutations survive: the masked URL of the crawler error (the base exception class masks the password again, so the test holds the result and not the layer) and the narrowing of the exception tuple of `retrieve_rag_context` (every failure that the fakes can raise is a `DevOpsCLIError`).

## Existing Tool Considered

The shared fakes and fixtures of #1307 (`web`, `qdrant`, `embedder`, `keyring_store`, `cli`, `config`) cover every edge of these tests. Hypothesis, syrupy and `pytest-httpserver` add nothing here: the tests need no new tool. The change builds one small helper, `tests/support/library_contracts.py`, which replaces a private function of the old drift test file and serves two test folders. It costs about 2,000 tokens to keep.

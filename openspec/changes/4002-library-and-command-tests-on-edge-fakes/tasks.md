# Tasks

## 1. The library tests mirror ai/library and run on the shared fakes (test-only edits)

- [x] 1.1 Split `tests/ai/library/test_docs_ingester.py` into `test_docs_ingest_local.py` and `test_docs_ingest_remote.py`, over the `web` fake and the public methods. Move its CLI cases to the `cli` fixture. Delete the model constructor test.
  Verification: `uv run pytest tests/ai/library/test_docs_ingest_local.py tests/ai/library/test_docs_ingest_remote.py tests/commands/test_ai_ingest_docs.py`
- [x] 1.2 Split `tests/ai/library/test_library_ingest.py` into `test_signature_extraction.py`, `test_library_contract_store.py` and `test_package_introspection.py`. Move its CLI cases to the `cli` fixture. Delete the two model constructor tests.
  Verification: `uv run pytest tests/ai/library/test_signature_extraction.py tests/ai/library/test_library_contract_store.py tests/ai/library/test_package_introspection.py tests/commands/test_ai_ingest_library.py`
- [x] 1.3 Move `tests/ai/analyze/test_library_drift_auditor.py` to `tests/ai/library/test_drift_findings.py` and `test_drift_report_saving.py`, with the shared demo contract in `tests/support/library_contracts.py`. Replace the patches of `Path.write_text` and of `analysis_directory` with real file system failures and the analysis directory variable. Move the CLI cases to `tests/commands/test_ai_audit_library_usage.py`.
  Verification: `uv run pytest tests/ai/library/test_drift_findings.py tests/ai/library/test_drift_report_saving.py tests/commands/test_ai_audit_library_usage.py`

## 2. The RAG command helper is tested through its public name (test-only edits)

- [x] 2.1 Delete `tests/ai/rag/test_ai_subcommands_rag.py`. Add `tests/commands/test_ai_retrieve_rag_context.py` for `retrieve_rag_context`, over the `qdrant`, `embedder` and `config` fixtures.
  Verification: `uv run pytest tests/commands/test_ai_retrieve_rag_context.py tests/ai/rag/test_investigation_context.py tests/commands/test_ai_cmd.py`

## 3. No patch, private import or private runner remains (test-only edits)

- [x] 3.1 Check that no migrated file patches, imports a private name or builds a `CliRunner`.
  Verification: `! git grep -n -e "patch(" -e "patch.object" -e "CliRunner" -e "_try_retrieve_rag_context" -e "import ai_app" -e "audit_library_usage_cmd" -- tests/ai/library tests/commands/test_ai_ingest_docs.py tests/commands/test_ai_ingest_library.py tests/commands/test_ai_audit_library_usage.py tests/commands/test_ai_retrieve_rag_context.py`
- [x] 3.2 Check that the four old files are gone.
  Verification: `! git ls-files -- tests/ai/library/test_docs_ingester.py tests/ai/library/test_library_ingest.py tests/ai/analyze/test_library_drift_auditor.py tests/ai/rag/test_ai_subcommands_rag.py`

## 4. Documents (documents)

- [x] 4.1 Check that the change folder is valid.
  Verification: `uv run devops openspec check`

## 5. Archive

- [x] 5.1 Archive the change.
  Verification: `uv run devops openspec archive 4002-library-and-command-tests-on-edge-fakes`

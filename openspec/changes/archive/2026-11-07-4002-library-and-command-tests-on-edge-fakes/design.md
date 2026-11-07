# Design

## Context

See proposal.md for the motivation and the scope (#4002, item 3 of #1329). The change is test-only. It touches no path under `src/`.

## Decisions

### 1. The drift report is written for real, and the failure is real

- **Decision**: the tests of a report that cannot be saved use the file system. A path below a regular file fails the `mkdir`. A read-only report file of an earlier run must be replaced, which only works because `DriftReport.save` removes the old file first.
- **Alternative considered**: keep `patch.object(Path, "write_text", side_effect=OSError(28, ...))`.
  - *Rejected*: it patches a method that the product code calls, so the test would pass if the product wrote the file with `os.write`.- **Alternative considered**: `resource.setrlimit(RLIMIT_FSIZE, 0)` to make the kernel refuse every write.
  - *Rejected*: opening a file for write truncates it first, so the old report is gone with or without the `unlink`. The test could not tell the two apart (the mutation survived). The limit also applies to the whole test process.

### 2. The analysis directory comes from its environment variable

- **Decision**: the audit command tests set `DEVOPS_CLI_DATA_ANALYSIS_DIR` with `monkeypatch.setenv`, then reset the settings cache with `reset_settings_cache`. The floor sets `DEVOPS_CLI_DATA_DIR`, and an environment variable beats the config file, so the `config` fixture cannot move `data.analysis_dir`.
- **Alternative considered**: patch `devops_cli.ai.analyze.cache.analysis_directory`, as the old test did.
  - *Rejected*: it patches a devops-cli name, which is what the item removes.

### 3. The command helper keeps a small test file of its own

- **Decision**: `retrieve_rag_context` of `commands/ai.py` gets `tests/commands/test_ai_retrieve_rag_context.py`. The investigation is held by `tests/ai/rag/test_investigation_context.py`, so the new file checks only what the helper adds: the `ai.rag.enabled` switch, the knowledge base check, and the answer of `None` when Qdrant refuses or the embedding model fails.
- **Alternative considered**: delete the two retrieval cases with the file and add nothing.
  - *Rejected*: no other test calls the helper, and the AI commands use it to ground their prompts.

### 4. The docs ingester tests stay on public methods

- **Decision**: the tests call `ingest_local_docs` and `ingest_remote_docs` and read the result and the chunk files. They name no private function and no HTML detail beyond a page that has a heading, a list, a link and navigation. Item 4 of #1329 can then change the HTML conversion with no test change.

### 5. Tests of a model constructor are deleted

- **Decision**: `DocChunk`, `ParameterSignature` and `FunctionSignature` are pydantic models. A test that builds one and reads back the same fields tests pydantic, not devops-cli. The extraction, store and ingest tests read these fields after real runs.

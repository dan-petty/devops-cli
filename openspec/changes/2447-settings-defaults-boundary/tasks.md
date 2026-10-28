# Tasks

## 1. A setting's default is read through the settings

- [x] Add a failing invariant: no module outside `config/` reads a `DEFAULT_*` name that a settings field takes as its default
  - Verification: `uv run devops ci test tests/invariants/test_source_tree.py`
- [x] Add failing tests: the chunk size and overlap, the RAG search defaults, the retriever defaults, the recorded analysis sampling, the audit destination, the GitHub cache directory, the Service state directory and the OSV digest directory follow a config file or a variable
  - Verification: `uv run devops ci test tests/config/test_setting_overrides_reach_their_readers.py`
- [x] Add `setting_default`, and move each of the 40 places to the loaded setting, `setting_default`, a required argument or a value of its own
  - Verification: `uv run devops ci test tests/config/ tests/invariants/ tests/test_ollama_dynamic_leasing.py tests/test_audit_stream.py tests/test_review_group_analysis.py`
- [x] Delete the copies of the cache defaults in `_resolve_llm_cache`
  - Verification: `uv run devops ci test tests/test_response_cache.py`
- [x] State the rule in `CONTRIBUTING.md`, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2447-settings-defaults-boundary`

## Workflow follow-up

- `LLMClient.chat` takes `temperature`, `top_p` and `seed` and does not use them: #2559.
- The OSV snapshot digest names a directory that is not osv-scanner's database: #2130.
- When #2447 merges, #1000 has all its parts: #2444, #2445 and #2447.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

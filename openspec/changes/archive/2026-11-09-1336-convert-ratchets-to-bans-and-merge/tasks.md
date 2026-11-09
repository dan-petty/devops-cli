# Tasks

## 1. Relocate Loose Root Test Helpers

- [x] 1.1 Move root test helper modules into `tests/support/`
  - Verification: `test ! -f tests/cluster_secret_fakes.py && test -f tests/support/cluster_secret_fakes.py`
- [x] 1.2 Update import statements across the test suite to use `tests.support.<module>`
  - Verification: `git grep -E "from tests\.(cluster_secret_fakes|copilot_review_payloads|github_token_samples|keyring_isolation|llm_stream_fakes|project_board_fake|project_reconcile_fake)" tests/ | wc -l`

## 2. Eliminate Invariant Private Imports and Patches

- [x] 2.1 Update `tests/invariants/test_dry_run_class_ratchet.py` to inspect commands from public `app` and remove module-level `CliRunner()`
  - Verification: `uv run pytest tests/invariants/test_dry_run_class_ratchet.py`
- [x] 2.2 Replace `fetch_secret_data` patch in `tests/invariants/test_k8s_manifests.py` with `process_fake`
  - Verification: `uv run pytest tests/invariants/test_k8s_manifests.py -k test_no_table_secret_is_copied_back_by_sync`

## 3. Implement Invariant Bans and Consolidate Subject Files

- [x] 3.1 Rename `tests/invariants/test_agents_md_claims.py` to `tests/invariants/test_agents_md.py` and add retired phrases ban
  - Verification: `uv run pytest tests/invariants/test_agents_md.py`
- [x] 3.2 Update `tests/invariants/test_source_tree.py` to convert ratchets to bans, delete ceiling constants, and add seed tests
  - Verification: `uv run pytest tests/invariants/test_source_tree.py`

## 4. Documentation and Quality Gates

- [x] 4.1 Update `docs/TESTING.md` and `AGENTS.md` with ban definitions and invariant subject files
  - Verification: `uv run pytest tests/invariants/test_agents_md.py`
- [x] 4.2 Verify OpenSpec gate passes
  - Verification: `uv run devops openspec check`
- [x] 4.3 Verify full CI suite passes
  - Verification: `uv run devops ci`

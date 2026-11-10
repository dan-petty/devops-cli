# Tasks

## 1. Make host-coupled tests portable to the built service image

Changes: `tests/sandbox/test_host_sandbox.py`, `tests/support/git_recording.py`, `tests/docs/test_docs_source_argv_collector.py`, `tests/docs/test_docs.py`, `tests/ai/test_run_store.py`.

- [x] 1.1 Update `tests/sandbox/test_host_sandbox.py`, `tests/support/git_recording.py`, `tests/docs/test_docs_source_argv_collector.py`, `tests/docs/test_docs.py`, and `tests/ai/test_run_store.py` so they pass inside `devops-cli-service:local` (`VERSION_CODENAME=trixie`, `USER 1000:1000`, `/app/.venv` wheel) and in source checkouts
  - Verification: `$ uv run devops ci test tests/sandbox/test_host_sandbox.py tests/core/test_git_contract.py tests/docs/test_docs_source_argv_collector.py tests/docs/test_docs.py tests/ai/test_run_store.py`

## 2. Run the test suite inside the built service image in CI and enforce the Debian invariant

Changes: `.github/workflows/ci.yml`, `tests/commands/test_ci.py`, `tests/invariants/test_architectural_invariants.py`.

- [x] 2.1 Add the 6-shard `service-image-test` job to `.github/workflows/ci.yml` and register its steps and job contract assertions in `tests/commands/test_ci.py`
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py tests/invariants/test_workflow_contracts.py`
- [x] 2.2 Add Debian distribution alignment and CI service-image test invariants plus mutation tests (`-k debian`) in `tests/invariants/test_architectural_invariants.py`
  - Verification: `$ uv run pytest tests/invariants/test_architectural_invariants.py -k debian`

# Tasks

## 1. Failing tests

- [x] Add failing tests in `tests/test_review_dry_run_preview.py` asserting dry-run preview matches real call requests across providers, reports missing Ollama configuration, and executes dry runs without spawning `gh` or touching real bus <!-- id: 0 -->
  - Verification: `uv run devops ci test tests/test_review_dry_run_preview.py`

## 2. Implementation

- [x] Support `transport` and `http_client` injection in `LLMClient` and `get_llm_client` factory <!-- id: 1 -->
  - Verification: `uv run devops ci test tests/test_ai_client_network.py`
- [x] Implement `_llm_request_preview` in `src/devops_cli/ai/review/runner.py` using `httpx2.MockTransport` recording <!-- id: 2 -->
  - Verification: `uv run devops ci test tests/test_review_dry_run_preview.py`
- [x] Prevent `_apply_github_token` from starting `gh` during dry-run in `src/devops_cli/core/process.py` and allow `XDG_RUNTIME_DIR`/`DBUS_SESSION_BUS_ADDRESS` <!-- id: 3 -->
  - Verification: `uv run devops ci test tests/test_process.py tests/test_cli_startup_imports.py`
- [x] Regenerate documentation <!-- id: 4 -->
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Verification and checks

- [x] Verify `fail-to-pass` check run against base <!-- id: 5 -->
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] Verify full CI checks pass <!-- id: 6 -->
  - Verification: `uv run devops ci`
- [x] Archive OpenSpec change <!-- id: 7 -->
  - Verification: `uv run devops openspec archive 1430-review-dry-run-request-preview`

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).

# Tasks

## 1. A refused backend URL keeps its credentials out of the sweep

- [x] Add a failing test: `run_level` with `ftp://user:s3cr3t@example.com/x?token=t0k3n` records a `ValueError` whose text holds neither `s3cr3t` nor `t0k3n`
  - Verification: `uv run devops ci test tests/test_ai_gateway_tune.py`
- [x] Raise a fixed `ValueError` text in `_validate_http_url`, with a comment that says why the module raises the standard library's `ValueError`
  - Verification: `uv run devops ci test tests/test_ai_gateway_tune.py`
- [x] Regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 909-gateway-bench-stdlib`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

# Tasks

## 1. Behavior

- [x] 1.1 Add invariant tests for kubectl CVE-2026-78661 entry in `tests/invariants/test_mcp_server_image.py`
  - Verification: `$ uv run devops ci test tests/invariants/test_mcp_server_image.py`
- [x] 1.2 Add `CVE-2026-78661 exp:2026-11-17` entry to `.trivyignore-mcp-server`
  - Verification: `$ uv run devops ci test tests/invariants/test_mcp_server_image.py`

## 2. Documents

- [x] 2.1 Validate OpenSpec changes
  - Verification: `$ uv run devops openspec check`

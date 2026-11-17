# Tasks

## 1. Renew the kubectl ignores

Kind: other. Reads: `.trivyignore-mcp-server`, `SECURITY.md`. Changes: `.trivyignore-mcp-server`.

- [x] 1.1 Renew the entries of CVE-2026-56851, CVE-2026-78669 and CVE-2026-78661 to 2026-11-20, with the renewal issue #6079 and the tracking issue #6084
  - Verification: `$ uv run devops ci test tests/invariants/test_mcp_server_image.py`

## Workflow follow-up

- Pending a person: check that the `MCP Server Image` check of the pull request passes.
- On 2026-11-20, bump kubectl if a stable release holds the fixes, else renew the three entries up to 2026-11-22: #6084.

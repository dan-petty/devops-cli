# Tasks

## 1. Pins and ignores

- [x] 1.1 Bump kubectl to 1.37.2 and helm to 4.3.1 in `tools.lock`; verify with `uv run pytest tests/tools_lock tests/invariants/test_mcp_server_image.py`
- [x] 1.2 Delete the entries of CVE-2026-78667 and CVE-2026-97031, and renew the other three to 2026-11-14; verify with `uv run pytest tests/invariants/test_mcp_server_image.py`

## Workflow follow-up

- Pending a person: check that the `mcp-server-image` check passes. Renew the three entries again on 2026-11-14 only if no fix exists, up to 2026-11-22.

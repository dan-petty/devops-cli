# Tasks

## 1. Pin helm 4.3.2

Kind: behavior. Reads: `src/devops_cli/tools_lock/tools.lock`, `.devcontainer/Dockerfile`, `tests/invariants/test_mcp_server_image.py`. Changes: `src/devops_cli/tools_lock/tools.lock`, `.devcontainer/Dockerfile`, `tests/invariants/test_mcp_server_image.py`.

- [x] 1.1 `tests/invariants/test_mcp_server_image.py::test_the_kubectl_and_helm_pins_hold_the_go_builds_that_fix_the_stdlib_findings` fails: it asserts helm 4.3.2 or newer, and that `.trivyignore-mcp-server` does not list CVE-2026-111943
  - Verification: `$ uv run devops ci test tests/invariants/test_mcp_server_image.py` fails on the base
- [x] 1.2 Bump helm to 4.3.2 in `tools.lock` and in `.devcontainer/Dockerfile`, with the digest of each archive from its `.sha256sum` file
  - Verification: `$ uv run devops ci test tests/invariants/test_devcontainer_config.py tests/tools_lock` passes

## 2. Renew the kubectl ignores

Kind: other. Reads: `.trivyignore-mcp-server`, `SECURITY.md`. Changes: `.trivyignore-mcp-server`.

- [x] 2.1 Delete the entry of CVE-2026-111943, and renew the entries of CVE-2026-56851 and CVE-2026-78669 to 2026-11-17 with the tracking issue #5582
  - Verification: `$ uv run devops ci test tests/invariants/test_mcp_server_image.py` passes

## Workflow follow-up

- Pending a person: check that the `MCP Server Image` check of the pull request passes.
- On 2026-11-17, bump kubectl if a release holds the fixes, else renew the two entries for 3 days, up to 2026-11-22: #5582.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

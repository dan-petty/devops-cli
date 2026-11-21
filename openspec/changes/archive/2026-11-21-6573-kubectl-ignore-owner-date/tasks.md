# Tasks

## 1. Extend the kubectl ignores

Kind: other. Reads: `.trivyignore.yaml`, `SECURITY.md`. Changes: `.trivyignore.yaml`.

- [x] 1.1 Set `expired_at: 2026-12-15` on the four kubectl entries, and name the owner decision and #6084 in each statement
  - Verification: `$ trivy rootfs --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 --ignorefile .trivyignore.yaml <root with usr/local/bin/kubectl>`

## Workflow follow-up

- Pending a person: check that the `MCP Server Image` check of the pull request passes.
- When a stable kubectl release holds the fixes, bump kubectl and delete the entries: #6084.

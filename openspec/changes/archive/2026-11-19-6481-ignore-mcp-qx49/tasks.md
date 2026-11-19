# Tasks

## 1. Ignore the advisory

Kind: other. Reads: `.osv-scanner-ignore.yaml`, `SECURITY.md`. Changes: `.osv-scanner-ignore.yaml`.

- [x] 1.1 Add the entry of GHSA-qx49-fqc8-xw99 for `src/devops_cli/tools_lock/semgrep.txt` to 2026-11-22, with the tracking issue #6480
  - Verification: `$ uv run devops ci --check --only audit`

## Workflow follow-up

- On 2026-11-22, bump Semgrep if a release takes `mcp` 1.30.0 or later, else renew the entry with new proof: #6480.

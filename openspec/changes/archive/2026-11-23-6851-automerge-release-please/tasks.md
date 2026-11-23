# Tasks

## 1. Workflows

- [x] 1.1 In `.github/workflows/release.yml`, remove the urgent fix check and enable auto-merge on every release pull request
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`

## 2. Documents

- [x] 2.1 Update `RELEASE_CYCLE.md` and `docs/adr/0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md` to document that auto-merge is armed on each release pull request
  - Verification: `$ uv run devops ci docs`

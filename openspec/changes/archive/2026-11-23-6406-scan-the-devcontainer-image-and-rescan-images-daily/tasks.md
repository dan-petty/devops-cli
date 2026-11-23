# Tasks

## 1. Action and Workflows
Kind: other.

- [x] 1.1 Add `upload-sarif` input to `.github/actions/image-scan/action.yml`
  - Verification: `uv run devops ci --check --only actionlint,zizmor`
- [x] 1.2 Add DevContainer image scan and SARIF upload to `.github/workflows/release.yml`
  - Verification: `uv run devops ci --check --only actionlint,zizmor`
- [x] 1.3 Add DevContainer image scan and upload job to `.github/workflows/devcontainer-image.yml`
  - Verification: `uv run devops ci --check --only actionlint,zizmor`
- [x] 1.4 Create `.github/workflows/image-rescan.yml` for daily image rescans
  - Verification: `uv run devops ci --check --only actionlint,zizmor`

## 2. Invariants and Checks
Kind: other.

- [x] 2.1 Update release DevContainer job assertion in `tests/commands/test_ci.py`
  - Verification: `uv run pytest tests/commands/test_ci.py -k test_the_release_attests -n 0`
- [x] 2.2 Verify workflow contracts pass
  - Verification: `uv run pytest tests/invariants/test_workflow_contracts.py -n 0`
- [x] 2.3 Verify OpenSpec specification check passes
  - Verification: `uv run devops openspec check`

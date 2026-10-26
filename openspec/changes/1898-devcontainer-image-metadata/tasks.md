# Tasks

## 1. Failing tests

- [x] 1.1 Add failing tests for image configuration and action build in `tests/test_devcontainer.py` and `tests/test_workflow_contracts.py`
  - Verification: `uv run devops ci test tests/test_devcontainer.py tests/test_workflow_contracts.py -k devcontainer_image`

## 2. Devcontainer image configuration and build action

- [ ] 2.1 Add `.devcontainer/image/devcontainer.json` and `.devcontainer/image/devcontainer-lock.json` without workspace mounts, lifecycle commands, or editor customizations
  - Verification: `uv run devops ci test tests/test_devcontainer.py -k devcontainer_image`
- [ ] 2.2 Update `.github/actions/devcontainer-image/action.yml` to build `.devcontainer/image/devcontainer.json`
  - Verification: `uv run devops ci test tests/test_workflow_contracts.py -k devcontainer_image`
- [ ] 2.3 Update telemetry and node version tests to include `.devcontainer/image/`
  - Verification: `uv run devops ci test tests/test_third_party_telemetry.py tests/test_devcontainer.py`

## 3. Verification and static checks

- [ ] 3.1 Verify the fail-to-pass check run passes against origin/main
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [ ] 3.2 Verify the full static checks and test suite pass
  - Verification: `uv run devops ci`

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).

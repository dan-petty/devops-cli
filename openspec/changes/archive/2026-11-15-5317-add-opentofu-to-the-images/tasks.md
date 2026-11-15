# Tasks

## 1. Pin OpenTofu

Reads: `src/devops_cli/tools_lock/tools.lock`, `.devcontainer/Dockerfile`, `Dockerfile`, `.github/workflows/ci.yml`.

Changes: `src/devops_cli/tools_lock/tools.lock`, `.devcontainer/Dockerfile`, `Dockerfile`, `.github/workflows/ci.yml`, `.devops/research-watch.toml`.

- [x] 1.1 Add the pin and each install path, and run the pin tests.
  - Verification: `$ uv run devops ci test tests/tools_lock tests/invariants/test_devcontainer_config.py`

## Workflow follow-up

- Pending a person: rebuild the images and confirm `tofu version` in each.

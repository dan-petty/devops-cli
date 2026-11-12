# Tasks

## 1. Updates

- [x] 1.1 Update the actions, the workflow images and the pre-commit hooks; tests read the pins
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor,lint`
- [x] 1.2 Update the Dockerfile bases and downloads and the devcontainer features
  - Verification: `$ uv run pytest -q tests/invariants tests/roadmap/test_roadmap_runner_tools.py`
- [x] 1.3 Update the tools-lock binaries and the Dev Containers CLI
  - Verification: `$ uv run pytest -q tests/tools_lock tests/commands/test_install_tools.py`
- [x] 1.4 Update OpenSpec to 1.17.0, write the skills again and record its runs inside pytest
  - Verification: `$ uv run devops openspec check`
- [x] 1.5 Update the cluster charts, images and Grafana plugins
  - Verification: `$ uv run devops ci --check --only k8s`
- [x] 1.6 Update the Python dependencies and hold google-genai below 3 for Renovate
  - Verification: `$ uv run pytest -q tests/core/test_renovate_config.py`

## 2. Migrations

- [x] 2.1 File one issue under #4893 for each update that needs work
  - Verification: `$ uv run devops gh issue view 4893`

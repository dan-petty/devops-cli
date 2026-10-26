# Proposal

## Why

Issue #1898: The published devcontainer image is built from the workspace configuration `.devcontainer/devcontainer.json`.
Dev Containers CLI writes the configuration attributes into the image label `devcontainer.metadata`.
Child repositories that use the published image read that label.
Consequently, child repositories inherit the `devops-cli` workspace settings:
- Volume mounts (`devops-cli-venv`, `devops-cli-data`, `devops-cli-uv`, cache volumes, and `global-devcontainer-home`).
- Workspace lifecycle commands (`devops devcontainer post-create` and `devops devcontainer post-start`).
- Editor extensions and settings (`ollama.endpoint`, formatting rules, and telemetry settings).

This causes child repositories to share virtual environments and volume mounts, or fail when running lifecycle commands intended only for the `devops-cli` repository.

## What Changes

- Add an image configuration at `.devcontainer/image/devcontainer.json` and its lockfile `.devcontainer/image/devcontainer-lock.json`.
  The image configuration specifies the Dockerfile build, features, `remoteUser: vscode`, and common container environment variables without workspace volume mounts, lifecycle commands, or editor customizations.
- Update `.github/actions/devcontainer-image/action.yml` to build from `.devcontainer/image/devcontainer.json` and generate `.devcontainer/image/devcontainer.build.json`.
- Add tests to ensure:
  - `.devcontainer/image/devcontainer.json` specifies no `mounts`, no lifecycle commands, and no `customizations`.
  - Feature sets and lockfiles of `.devcontainer/image/` and `.devcontainer/` match.
  - The shared action `.github/actions/devcontainer-image` builds the image configuration.
- The change sets `skip_specs: true` in `.openspec.yaml` because it modifies internal container image build configuration and CI actions without changing `devops` CLI commands, manifests, or public service interfaces.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Infrastructure / CI: `.devcontainer/image/devcontainer.json`, `.devcontainer/image/devcontainer-lock.json`, `.github/actions/devcontainer-image/action.yml`.
- Tests: `tests/test_devcontainer.py`, `tests/test_workflow_contracts.py`, `tests/test_third_party_telemetry.py`.

## Feasibility

- Confirmed with `@devcontainers/cli` 0.89.0: `devcontainer read-configuration --workspace-folder . --config .devcontainer/image/devcontainer.json` resolves the nested configuration and resolves Dockerfile `../Dockerfile` and context `../..` correctly.
- Confirmed with upstream Dev Containers prebuild specification (https://containers.dev/guide/prebuild) that separating the image build configuration from the user workspace configuration prevents workspace metadata pollution in child containers.
- Confirmed that `devcontainer build` passes `--frozen-lockfile` against `.devcontainer/image/devcontainer-lock.json` when the configuration is in `.devcontainer/image/`.

## Existing Tool Considered

Dev Containers CLI provides native support for multiple configurations per repository and reading configurations from subdirectories (`.devcontainer/<folder>/devcontainer.json`).
Using this upstream feature avoids custom build scripts, post-build label stripping hacks, or secondary repositories.
The internal code that the change deletes: none.

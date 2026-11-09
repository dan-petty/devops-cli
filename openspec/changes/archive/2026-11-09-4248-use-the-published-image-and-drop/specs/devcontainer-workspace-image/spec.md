# Spec Delta

## Purpose
The devcontainer of this repository: it uses the published image, mounts no cache volume, and keeps the mounts that hold data across rebuilds.

## ADDED Requirements

### Requirement: The workspace devcontainer uses the published image
`.devcontainer/devcontainer.json` SHALL name `CONST_DEVCONTAINER_PUBLISHED_IMAGE` in `image`, and SHALL have no `build` and no `features`. Its `containerEnv`, when present, SHALL hold no key of the `containerEnv` of `.devcontainer/image/devcontainer.json`. `.devcontainer/devcontainer-lock.json` SHALL NOT exist.

#### Scenario: The workspace configuration names the image
- **WHEN** a test reads `.devcontainer/devcontainer.json` and `.devcontainer/image/devcontainer.json`
- **THEN** `image` is `CONST_DEVCONTAINER_PUBLISHED_IMAGE`
- **AND** the workspace configuration has no `build` and no `features`
- **AND** no `containerEnv` key of the image configuration is in the workspace configuration
- **AND** `.devcontainer/devcontainer-lock.json` does not exist

### Requirement: The workspace devcontainer mounts no cache volume
`.devcontainer/devcontainer.json` SHALL mount no volume on `.venv`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache` or `.uv` of the workspace, and SHALL NOT set `UV_CACHE_DIR`.

#### Scenario: No mount targets a cache folder
- **WHEN** a test reads the `mounts` of `.devcontainer/devcontainer.json`
- **THEN** no mount has a target in the workspace folder named `.venv`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache` or `.uv`
- **AND** the configuration sets no `UV_CACHE_DIR`

### Requirement: The workspace devcontainer keeps the mounts that hold data
`.devcontainer/devcontainer.json` SHALL keep the volume `devops-cli-data` on `.data` of the workspace, the volume `global-devcontainer-home` on `/home/vscode`, the volume `devops-cli-tmp` on `/tmp`, and the bind mount of the host `.ssh` folder on `/home/vscode/.ssh`.

#### Scenario: The data mounts are present
- **WHEN** a test reads the `mounts` of `.devcontainer/devcontainer.json`
- **THEN** the list holds each of the four mounts with its source, target and type

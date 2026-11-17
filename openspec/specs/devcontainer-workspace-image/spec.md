# devcontainer-workspace-image Specification

## Purpose
The devcontainer of this repository: it uses the published image, mounts no cache volume, and keeps the mounts that hold data across rebuilds.

## Requirements

### Requirement: The workspace devcontainer uses the published image
`.devcontainer/devcontainer.json` SHALL name `CONST_DEVCONTAINER_PUBLISHED_IMAGE` in `image`, and SHALL have no `build` and no `features`. Its `containerEnv`, when present, SHALL hold no key of the `containerEnv` of `.devcontainer/image/devcontainer.json`. `.devcontainer/devcontainer-lock.json` SHALL NOT exist.

#### Scenario: The workspace configuration names the image
- **WHEN** a person runs `uv run devops devcontainer validate`
- **THEN** it prints `Base:` with the published image `ghcr.io/dan-petty/devops-cli/devcontainer:latest`, the value of `CONST_DEVCONTAINER_PUBLISHED_IMAGE`, and `Features: 0 configured`
- **AND** `git ls-files .devcontainer/devcontainer-lock.json` prints nothing
- **AND** in the workspace container, `printenv` shows each variable of the `containerEnv` of `.devcontainer/image/devcontainer.json` with the value of the image

### Requirement: The workspace devcontainer mounts no cache volume
`.devcontainer/devcontainer.json` SHALL mount no volume on `.venv`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache` or `.uv` of the workspace, and SHALL NOT set `UV_CACHE_DIR`.

#### Scenario: No mount targets a cache folder
- **WHEN** a person runs `findmnt -rn -o TARGET` in the workspace container
- **THEN** no target is the folder `.venv`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache` or `.uv` of the workspace
- **AND** `printenv UV_CACHE_DIR` prints nothing

### Requirement: The workspace devcontainer keeps the mounts that hold data
`.devcontainer/devcontainer.json` SHALL keep the volume `devops-cli-data` on `.data` of the workspace, the volume `global-devcontainer-home` on `/home/vscode`, the volume `devops-cli-tmp` on `/tmp`, and the bind mount of the host `.ssh` folder on `/home/vscode/.ssh`.

#### Scenario: The data mounts are present
- **WHEN** a person runs `findmnt -rn -o TARGET,SOURCE` in the workspace container
- **THEN** `.data` of the workspace, `/home/vscode`, `/tmp` and `/home/vscode/.ssh` are mount targets
- **AND** the sources of the first three name the volumes `devops-cli-data`, `global-devcontainer-home` and `devops-cli-tmp`, and the source of `/home/vscode/.ssh` is the `.ssh` folder of the host

# Proposal: #4248

## Why

Closes #4248. `.devcontainer/devcontainer.json` builds the image of this repository on each workstation: it builds `.devcontainer/Dockerfile` and installs 7 Dev Container Features. `.devcontainer/image/devcontainer.json` holds the same build for the published image (#2309). The two files have the same `features`, the same lock file, and the same `containerEnv` except `UV_CACHE_DIR`, so each image change is made two times, and each rebuild runs apt on `debian:sid` and all 7 features again.

The workspace configuration also mounts five cache volumes (`.venv`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.uv`). They were for a workspace on a slow Windows mount. The workspace is now on the WSL file system, on the same ext4 device as the volumes, so they give no speed.

## What Changes

- `.devcontainer/devcontainer.json` names the published image `ghcr.io/dan-petty/devops-cli/devcontainer:latest` (`CONST_DEVCONTAINER_PUBLISHED_IMAGE`) in place of `build`. It has no `features` and no `containerEnv`: the `devcontainer.metadata` label of the image gives the features, their run options, the remote user and every environment entry.
- `.devcontainer/devcontainer-lock.json` is deleted. It is equal to `.devcontainer/image/devcontainer-lock.json`, which stays with the one build definition.
- The five cache volumes and `UV_CACHE_DIR` are removed. The folders are in `.gitignore`. uv keeps its cache in `~/.cache/uv` on the home volume.
- The mounts that hold data stay unchanged: the `.data` volume, the home volume, the `.ssh` bind mount and the `/tmp` volume.
- `devops research inventory` reads the lock of each configuration folder (`.devcontainer/<folder>/devcontainer-lock.json`) as well as `.devcontainer/devcontainer-lock.json`. Without this, the inventory of this repository loses its feature pins, which now are only in `.devcontainer/image/devcontainer-lock.json`.
- New invariant tests: the workspace configuration names the published image and repeats nothing of the image configuration, mounts no cache volume, and keeps the four data mounts.
- `docs/DEVCONTAINER_USAGE.md` and `CONTRIBUTING.md` say where the image is built, how this repository gets a new release, how to try an image change before a release, and how to remove the old cache volumes by name.

The workspace configuration is observable (the `devcontainer-process-limit` capability already covers it), so the change carries a spec delta.

## Capabilities

### New Capabilities

- `devcontainer-workspace-image`: the workspace devcontainer uses the published image, mounts no cache volume, and keeps the mounts that hold data.

### Modified Capabilities

- `research-inventory`: the inventory reads the devcontainer lock of each configuration folder.

## Impact

- `.devcontainer/devcontainer.json`, `.devcontainer/devcontainer-lock.json` (deleted), `.devcontainer/Dockerfile` (a comment), `src/devops_cli/research/container_pins.py`, `tests/invariants/test_devcontainer_config.py`, `tests/commands/test_devcontainer.py`, `tests/research/test_inventory.py`, `docs/DEVCONTAINER_USAGE.md`, `CONTRIBUTING.md`.
- A rebuild pulls the image in place of a local build. An image change reaches this workspace only after a release publishes it; CI still builds and starts the image for each pull request that changes `.devcontainer` or `src`.
- The first lifecycle commands after the rebuild run the image's `devops` copy until `uv sync` fills `.venv` (#2449).
- The change fits one pull request.

## Feasibility

- The `devcontainer.metadata` label of `ghcr.io/dan-petty/devops-cli/devcontainer:latest` (v0.101.0, `linux/amd64`, read with an anonymous registry token on 2026-11-09) holds the 7 features with their run options (docker-in-docker: `privileged`, `entrypoint` and a mount), `remoteUser: vscode` and the full `containerEnv`. It keeps `${containerWorkspaceFolder}` for the container start to resolve.
- `jq` comparison of the two configurations: equal `features`, equal lock files, and equal `containerEnv` except `UV_CACHE_DIR`.
- `findmnt` in the devcontainer: the workspace bind mount and every named volume are on the same ext4 device.
- `.gitignore` holds `.venv`, `.uv/`, `.mypy_cache/`, `.pytest_cache/` and `.ruff_cache/`.

## Existing Tool Considered

The prebuilt-image pattern of the Dev Container specification (<https://containers.dev/guide/prebuild>) and the image metadata label that the Dev Containers CLI writes. The change deletes configuration and builds nothing: the workspace `build` and `features` blocks, 28 duplicated `containerEnv` entries, the duplicated lock file and five cache mounts.

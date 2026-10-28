# Proposal

## Why

Issue #2449: In the devcontainer of this repository, `devops` on `PATH` is the copy of the package that the image installed when it was built. `.devcontainer/Dockerfile` installs `src/` into the system site-packages (`uv pip install --system --break-system-packages --no-deps /tmp/devops-cli`), and `/usr/local/bin/devops` runs that copy. `.devcontainer/devcontainer.json` sets no `PATH`. So a terminal where the `.venv` of the workspace is not active runs the copy of the image's commit. That copy does not have the changes that merged after the image build. `devops config set firecrawl.api_key` failed with "Unknown configuration key", and `devops k8s push-secrets` asked for a secret that the checkout removed. `uv run devops` ran both commands correctly.

## What Changes

- `.devcontainer/devcontainer.json` sets `remoteEnv.PATH` to `${containerWorkspaceFolder}/.venv/bin:${containerEnv:PATH}`. Terminals, tasks and the lifecycle commands of the devcontainer then find `.venv/bin/devops`, the editable install of the checkout, before `/usr/local/bin/devops`. A merge then needs no image rebuild.
- The image keeps the dependency layer and the system install of the package. Child repositories and the first post-create of this repository use that copy (see Feasibility).
- `.devcontainer/image/devcontainer.json`, the configuration of the published image, sets no `remoteEnv`. A child repository keeps the `devops` of the image.
- A new invariant test, `tests/invariants/test_devcontainer_config.py`, parses both configurations and holds the two values.
- A comment in `.devcontainer/Dockerfile` and step 2 of the README quick start tell which `devops` runs where.
- The change sets `skip_specs: true` in `.openspec.yaml`. It changes the development environment of this repository only. No `devops` command, option, message, manifest or service changes, and the published image does not change.
- This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Development environment: `.devcontainer/devcontainer.json`, a comment in `.devcontainer/Dockerfile`.
- Documents: `README.md`.
- Tests: `tests/invariants/test_devcontainer_config.py`.

## Feasibility

- Command output in this devcontainer: `/usr/local/bin/devops --version` gives `devops-cli 0.3.1`, and `/usr/bin/python3` imports `devops_cli` from `/usr/local/lib/python3.14/dist-packages`. `.venv/bin/devops --version` in the checkout gives `devops-cli 0.9.0`.
- Consumers of the system install, found with `git grep -n -i devcontainer .github` and a search of the scaffold and its documents:
  - The release publishes the image as `ghcr.io/dan-petty/devops-cli/devcontainer` for child repositories (`.github/workflows/release.yml`, `docs/DEVCONTAINER_USAGE.md`). `devops devcontainer init --published` writes a `devcontainer.json` that names only the image and runs `devops devcontainer post-create` and `devops devcontainer post-start` (`src/devops_cli/templates/devcontainer.json.j2`). A child repository has no devops-cli in its own `.venv`, so these commands need the copy of the image.
  - `.github/actions/devcontainer-smoke` runs `devops --version` in the image as `vscode`. The `DevContainer Image` check of `ci.yml` and the release run this action.
  - This repository's `postCreateCommand` runs `devops devcontainer post-create`. On a new `devops-cli-venv` volume the `.venv` is empty, and post-create does not run `uv sync`, so the first post-create needs the copy of the image.
  - No workflow job runs in the image (`git grep -n "container:" .github` finds no job container). CI on a GitHub runner runs `uv run devops`, which this change does not touch.
  - The MCP configurations run `uv run --with fastmcp devops`, which uses the project environment, not the system copy.
  So the system install stays, and the fix is in `PATH` only.
- Dev Containers CLI 0.89.0 source (`dist/spec-node/devContainersSpecCLI.js`): the remote environment of the lifecycle commands, `devcontainer exec` and the editor is `{...probedShellEnv, ...remoteEnv}`, and `${containerEnv:VAR}` reads the container's own environment. So `remoteEnv.PATH` applies to terminals and to `postCreateCommand` and `postStartCommand`.
- Command output: `devcontainer read-configuration --workspace-folder <worktree>` (Dev Containers CLI 0.89.0) resolves `remoteEnv.PATH` to `/workspaces/<folder>/.venv/bin:${containerEnv:PATH}`. The CLI replaces `${containerEnv:PATH}` when the container runs.
- Debian's `/etc/zsh/zshenv` sets `PATH` only when it is empty or `/bin:/usr/bin`, and `/etc/zsh/zprofile` sets nothing. So the default zsh terminal keeps the `PATH` of `remoteEnv`.

## Existing Tool Considered

The `remoteEnv` property of the Dev Container specification (<https://containers.dev/implementors/json_reference/>) and the project environment that `uv sync` writes into `.venv` cover the need. The specification shows the same pattern: `"remoteEnv": { "PATH": "${containerEnv:PATH}:/some/other/path" }`. The change builds nothing and deletes no internal code.

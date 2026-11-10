# Proposal: #4359

## Why

In the devcontainer, `devops roadmap plan-check <n>` fails with `Required dependency 'openspec' is not installed or not available in PATH`. Post-create installs the locked tools into `~/.local/bin`, which is not on `PATH`, and it installs them again at each container creation. A tool belongs in the image, in a standard location, so that it is on `PATH` with no setting and a rebuild of the image is the one way to change it. Closes #4359.

## What Changes

- The devcontainer image build runs `devops install-tools` for every tool of `tools.lock`. Each command links into `/usr/local/bin`. The files of a Python or Node tool are in `/usr/local/share/devops-cli`.
- `devops devcontainer post-create` installs no locked tool. The option `--skip-tools`, the install step of the post-create plan and `_bootstrap_managed_tools` are removed.
- The change alters a devops option and the contents of the image, which a consumer observes, so it carries a spec delta.
- The change fits one pull request.

## Capabilities

- New: `devcontainer-image-tools`.

## Impact

- Users of the devcontainer get `openspec` and every other locked tool on `PATH` after a rebuild of the image.
- A child repository that uses the published image gets the same tools. A project on another image installs them with `devops install-tools`.
- The build of the image downloads the tools, so it takes longer after a source change.

## Feasibility

Confirmed on 2026-11-10 in the devcontainer: `uv run devops install-tools --tool openspec --only-missing` links `~/.local/bin/openspec`, `openspec --version` prints `1.14.3` once that folder is on `PATH`, and `devops roadmap plan-check` stops with the error of the issue without it. `src/devops_cli/commands/install_tools.py` takes `--target-dir`, and `tool_install_dir` takes its root from `DEVOPS_CLI_USER_DATA_ROOT`, which the root `Dockerfile` already sets for the same command. The image build itself is not run: the registry of this environment refused the base image pull, so the CI image build is the check.

## Existing Tool Considered

`devops install-tools` and the root `Dockerfile` pattern. The change adds no installer: it calls the existing one at build time.

# Proposal: #4359

## Why

In the devcontainer, `devops roadmap plan-check <n>` fails with `Required dependency 'openspec' is not installed or not available in PATH`. Post-create installs the locked tools into `~/.local/bin`, which is not on `PATH`, and it installs them again at each container creation. A tool belongs in the image, in a standard location, so that it is on `PATH` with no setting and a rebuild of the image is the one way to change it. Closes #4359.

## What Changes

- The devcontainer image build gets every tool of `tools.lock` with native steps: `curl` with `sha256sum -c` in a builder stage for each of the 20 binaries, `uv pip sync --require-hashes` for each Python tool and `npm ci --ignore-scripts` in a pinned Node stage for each Node tool. Each command is in `/usr/local/bin`. The files of a Python or Node tool are in `/usr/local/share/devops-tools`. No custom installer runs in the build.
- `devops devcontainer post-create` installs no locked tool. The option `--skip-tools`, the install step of the post-create plan and `_bootstrap_managed_tools` are removed.
- The change alters a devops option and the contents of the image, which a consumer observes, so it carries a spec delta.
- The change fits one pull request.

## Capabilities

- New: `devcontainer-image-tools`.

## Impact

- Users of the devcontainer get `openspec` and every other locked tool on `PATH` after a rebuild of the image.
- A child repository that uses the published image gets the same tools. A project on another image installs them with `devops install-tools`.
- The tool steps depend only on the lock files they copy, so a source change of this repository rebuilds none of them.
- The Dockerfile holds the url and the sha256 of each binary for both Linux architectures. Until the follow-up items remove `tools.lock`, a test fails when the two differ.

## Feasibility

Confirmed on 2026-11-10 in the devcontainer: `uv run devops install-tools --tool openspec --only-missing` links `~/.local/bin/openspec`, `openspec --version` prints `1.14.3` once that folder is on `PATH`, and `devops roadmap plan-check` stops with the error of the issue without it. The root `Dockerfile` already checks a download with `sha256sum -c`, and `tools.lock` holds the url and sha256 of each binary for `linux-amd64` and `linux-arm64`. The image build itself is not run: the registry of this environment refused the base image pull, so the CI image build is the check.

## Existing Tool Considered

`ADD --checksum`, `curl` with `sha256sum -c`, `uv pip sync --require-hashes` and `npm ci`: the native steps of Docker and of each package manager. The change adds no installer. Its follow-up items move the root `Dockerfile` and the CI off `devops install-tools`, move the product code to a `PATH` lookup, and remove the command and `tools.lock`.

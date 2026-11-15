# Proposal

## Why

The GitHub settings stacks and the drift job need `tofu`, and no image or CI job holds it. `tofu` was not installed in the devcontainer, the runner image or CI (#5317).

## What Changes

- Add `[binary.tofu]` 1.13.9 to `src/devops_cli/tools_lock/tools.lock` with the sha256 of the linux-amd64 and linux-arm64 zip builds.
- Add a native step to the `tools` stage of `.devcontainer/Dockerfile`, with a sha256 check and `unzip`.
- Install the pin in the runner image and in the CI test job with `devops install-tools --tool tofu`.
- Watch `opentofu/opentofu` releases so Renovate updates the pin.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `devcontainer-image-tools`: OpenTofu is a pinned tool of both images and of CI.

## Impact

- Tool lock: `src/devops_cli/tools_lock/tools.lock`
- Images: `.devcontainer/Dockerfile`, `Dockerfile`
- CI: `.github/workflows/ci.yml`
- Watch list: `.devops/research-watch.toml`

## Feasibility

- Read on `origin/main`, 2026-11-15. The release checksums file gives the two digests, and `devops install-tools --tool tofu --target-dir <dir>` prints `OpenTofu v1.13.9`.
- `unzip` is already in the `tools` stage.
- `uv run python -m pytest tests/tools_lock tests/invariants/test_devcontainer_config.py tests/research/test_watch_list.py` passes with 124 tests.

## Existing Tool Considered

The pinned download steps of the image builds and `devops install-tools`, as for kubectl, helm, trivy and vale.

## Dependencies

None.

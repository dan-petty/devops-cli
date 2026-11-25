# Proposal: #7202

## Why
The smoke checks of the images were `docker run` lines in `ci.yml`, and the same lines again in `release-image.yml`. No developer could run them with one command. Owner direction of 2026-11-25: build testing and validation of Docker images happens in a Docker layer when possible.

## What Changes
- A new `smoke.Dockerfile` has one stage for each image: `service-smoke`, `mcp-server-smoke`, `runner-smoke` and `uv-seed-smoke`.
- The checks of the user, the tool versions, the absent build tools, the runner tools and the offline sync of the uv seed are `RUN` steps of these stages.
- `ci.yml` builds the stages on the loaded images, and `release-image.yml` builds them on the pushed digest.
- A `docker run` stays only for what a `RUN` step cannot make: the entrypoint, `/healthz`, the read-only root file system with all capabilities dropped, and the size bounds.
- The pull request now runs the uv seed check of the release too, so a pull request finds that failure before the release does.
- The build context holds `.python-version`, which the uv seed check reads as a checkout does.

## Capabilities
- `container-image-layers`: new requirement for the smoke stages.
- `mcp-server-image`, `roadmap-implement-runner`, `roadmap-service-deployment`: the checks that named a `docker run` name the stage.

## Impact
No published image changes. No stage of `smoke.Dockerfile` is published. The image jobs build one more small file for each image.

## Feasibility
- A stage can start FROM an earlier stage only, and `service` stays the last stage of `Dockerfile`. So the smoke stages are in their own file.
- `FROM` takes a build argument, so one stage text starts from a local tag or from a pushed digest.
- The stages build with Podman 5.8 in the devcontainer, and with BuildKit in the image jobs.

## Existing Tool Considered
Docker BuildKit stages and build arguments cover the need. `container-structure-test` and `goss` run a container outside the build, so they give no build layer and add a tool.

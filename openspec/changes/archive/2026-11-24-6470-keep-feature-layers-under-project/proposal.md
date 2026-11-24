# Proposal: #6470

## Why
The Dev Containers CLI adds the Dev Container Feature layers after the last stage of `.devcontainer/Dockerfile`. The project layer (`COPY --link` of the package) is in the last stage, so every change to `src/` rebuilds both Feature layers (`common-utils` and `podman-in-podman`). A local cold build takes 67 seconds and 46 MiB compressed for those layers. Each release pushes them as new layers, defeating registry layer caching. Closes #6470.

## What Changes
- Add `ARG BASE_IMAGE=base` at the top of `.devcontainer/Dockerfile`.
- Define a `base` stage in `.devcontainer/Dockerfile` that holds base tools, dependencies, and user vscode without the project package.
- Define a `builder` stage that installs `devops-cli` into a temporary location.
- Define a `project` stage starting `FROM ${BASE_IMAGE}` that copies package files from `builder` and sets `USER vscode`.
- Update `.github/actions/devcontainer-image/action.yml` to run the Dev Containers CLI build targeting `base`, push by digest, then build the `project` stage with `docker buildx build --target project --build-arg BASE_IMAGE=<feature-digest>` and output the project digest.
- Update `docs/SDLC.md` and `docs/DEVCONTAINER_USAGE.md` to document the two-stage build flow.

## Capabilities
- Base image build without project files via `docker buildx build --target base`.
- Project layer build on top of any base digest via `docker buildx build --target project --build-arg BASE_IMAGE=...`.
- Dev Container Feature layer caching across releases that modify only source code.

## Impact
- Devcontainer build action executes two build steps: Feature base build, then project build.
- GitHub Actions workflows (`devcontainer-image.yml`, `release.yml`) continue to consume the single final digest output from the action.
- Releases changing only `src/` hit Feature layer cache and push only the project layer.

## Feasibility
- Tested BuildKit multi-stage builds with `ARG` before `FROM`.
- Dev Containers CLI supports `.build.target` in `devcontainer.json`.
- BuildKit supports `--build-arg BASE_IMAGE=<image>@<digest>`.

## Existing Tool Considered
The alternatives check records `not-applicable` (perf class, no external tool). The change uses existing Dev Containers CLI 0.90.0 and `docker buildx`.

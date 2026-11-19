# Proposal: #6414

## Why
The `DevContainer Image` job averages 386 s, over the limit of 5 min plus 1 min of AGENTS.md rule 5 (#6414). `.devcontainer/Dockerfile` downloads and checks each tool by hand, and `.devcontainer/image/devcontainer.json` adds seven Dev Container Features with copied version pins. The `docker-in-docker` Feature is frozen at 2.17.0 and does not support `debian:sid`, so the Dockerfile rewrites `/etc/os-release`. The `GIT_CONFIG_*` entries of `containerEnv` give four `SecretsUsedInArgOrEnv` build-check warnings. The owner decisions of 2026-11-19 are: the image builds FROM the devtools image by digest, and Podman replaces Docker, with no Docker CLI in the container.

## What Changes
- `.devcontainer/Dockerfile` builds FROM `ghcr.io/dan-petty/devtools:<date>@sha256:<digest>`. A `lock` stage exports the hashed requirements of `uv.lock`. A venv layer installs them with `--require-hashes` in `/opt/devops-cli/.venv`, the last directory of `PATH`. The project is the last layer (`COPY --link`), then `USER vscode`. The file has `# check=error=true`. The actionlint, tools and npm-tools stages, the tool venvs, the `/etc/os-release` rewrite and the unpinned pre-commit install go.
- A `devcontainers-cli` stage holds only the Dev Containers CLI of the devtools image. The build action exports it and builds with it, and the smoke action copies the CLI from the image that it starts. The actions run no `devops install-tools`, and the two workflows install no uv for them.
- `.devcontainer/image/devcontainer.json` keeps `common-utils:2` and adds `podman-in-podman:1` with `dockerCompat`. The other five Features go. The `GIT_CONFIG_*` entries move to `remoteEnv`, with `DOCKER_HOST=unix:///var/run/docker.sock`. `DOCKER_CLI_HINTS` goes: no Docker CLI reads it. `devcontainer upgrade` writes the lockfile again.
- The smoke action checks the user, `devops` from the venv, the tools of the devtools image, `ping`, `docker` (Podman), the rootful API socket and the order of the credential helpers. The step that calls it has `timeout-minutes`.
- The `tools_lock` path filter of `devcontainer-image.yml` goes: `.devcontainer/Dockerfile` pins the devtools image.
- Renovate groups the devtools image for each manager, and the Python-minor custom manager of the devcontainer Dockerfile goes. The descriptions that name devcontainer copies change.
- The pin-comparison test of `tests/invariants/test_devcontainer_config.py` goes, and its count in `config_reads.toml` falls to 1.
- The devcontainer image is observable to its users, so the change has spec deltas of `devcontainer-image-tools` and `ci-devcontainer-image`.

## Capabilities
- `devcontainer-image-tools`: modified. The tools come from the devtools image; the venv, Podman and the credential helpers are new requirements.
- `ci-devcontainer-image`: modified. The path filter has no tool lock, and the build uses the CLI of the devtools image.
- `devcontainer-workspace-image`, `cloudflared-release-pin` and `tflint-release-pin`: no change. Their requirements name no part of the devcontainer image that this change touches.

## Impact
- The owner's devcontainer and every agent session start from the new image after the next release. `docker` is Podman, and there are two image stores: the rootless store of `docker` and `podman`, and the rootful store of the Docker SDK of `devops docker`. `podman save <image> | sudo podman load` copies an image from the first to the second.
- The old `dind-var-lib-docker-*` volumes become orphans on the host.
- The docker driver of Minikube with `podman-docker` is not tested (#6466).
- Podman refuses the `--tmpfs <path>:uid=1000,gid=1000` option of the image smoke steps of `ci.yml` and `release.yml`, so these steps run on a GitHub-hosted runner but not in the devcontainer (#6468).
- The Dev Containers CLI adds the Feature layers after the project layer, so a change of `src/` builds them again (#6470).
- The start on the owner's rootless Podman host is a check for a person after the release (#6471).
- The change fits one pull request.

## Feasibility
- `docker buildx imagetools inspect ghcr.io/dan-petty/devtools:20261119` with no credentials returned the index `sha256:a7b2f111941beaf5d36efb19f6ed2a50f8bed3062003498b97523da926143c51` for `linux/amd64` and `linux/arm64`, so the image is public.
- The tag list of `ghcr.io/dan-petty/devcontainer-features/podman-in-podman` with no credentials holds `1` and `1.0.0`, and its `devcontainer-feature.json` has the options `dockerCompat` and `compose` (default `podman-compose`).
- The devtools image has `uv`, `python3.14` (`/usr/bin/python3`), Node.js 24, `podman` and the Dev Containers CLI 0.90.0 in `/usr/local/lib/devtools/npm/node_modules/@devcontainers/cli`. That package has no dependencies, so Node.js on the runner runs it.
- The Dev Containers CLI 0.90.0 puts the line `ARG _DEV_CONTAINERS_BASE_IMAGE=scratch` before the user Dockerfile, so `# check=error=true` applies to a plain `docker buildx build` of the file. A plain build of the file with BuildKit 0.34.2 gave no build-check warning.
- A local `devcontainer build` with the action's options and `devcontainer up` with the Feature ran in the devcontainer on Docker; the pull request comment holds the times.

## Existing Tool Considered
- The Dev Containers CLI (devcontainers/cli, MIT, maintained) builds the image with its Features and pushes it by digest with a metadata file. The change takes it from the devtools image and builds nothing new.
- The `devcontainers/ci` action has no push-by-digest output and no `--metadata-file` pass-through, so it cannot keep the release flow that starts the digest before it tags it.
- The `podman-in-podman` Feature covers Podman with a Docker-compatible socket and command.
- The change deletes internal code: the hand download stages of `.devcontainer/Dockerfile`, the copied Feature pins, the `devops install-tools` steps of the two actions and the pin-comparison test.

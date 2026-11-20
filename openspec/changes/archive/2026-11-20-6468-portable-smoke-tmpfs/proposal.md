# Proposal: #6468

## Why

The image smoke steps of `.github/workflows/ci.yml` and `.github/workflows/release.yml` start containers with `--tmpfs /home/devops:uid=1000,gid=1000`. Docker gives these options to the kernel. Podman 5.8.6 checks the options and stops with `Error: unknown mount option "uid=1000": invalid mount option`. Thus the steps run on a GitHub-hosted runner, but not in the devcontainer of #6414, where `docker` is `podman-docker`. The rule of `docs/SDLC.md` says that every CI job runs in the devcontainer and on a stock GitHub-hosted runner. Closes #6468.

## What Changes

- Replace `--tmpfs /home/devops:uid=1000,gid=1000` with `--tmpfs /home/devops:mode=1777` in the 8 `docker run` commands of the image smoke steps: the Service image and the runner image steps of `ci.yml` and of `release.yml`. The 2 commands that also set `exec,size=3g` keep these options and become `mode=1777,exec,size=3g`.
- The change alters no behavior that a consumer observes: it changes CI workflows only. Thus it has no spec delta, and `.openspec.yaml` sets `skip_specs: true`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Workflows: `.github/workflows/ci.yml`, `.github/workflows/release.yml`.
- The home of the smoke containers is `root 1777`, not `devops 755`. User `devops` (1000) still writes its files there, like it writes the `emptyDir` home of a pod (mode 0777).
- No document names the old option, so no document changes.

## Feasibility

- In the devcontainer, rootless Podman 5.8.6 through `podman-docker`, on the published Service image: `--tmpfs /home/devops:uid=1000,gid=1000` stops with `unknown mount option "uid=1000"`, and `--tmpfs /home/devops:mode=1777` exits 0 with the Python probe of the Service Image Smoke Test (issue comment of 2026-11-20).
- `mode` is a tmpfs mount option of the kernel. Docker gives it to the kernel, and Podman accepts it.
- The image-change filters of the jobs `service-image` and `runner-image` of `ci.yml` watch `.github/workflows/ci.yml`, so this pull request runs both smoke steps with Docker on a GitHub-hosted runner.

## Existing Tool Considered

The alternatives check of 2026-11-20 records `not-applicable` for class ci and names no tool. The workflows already use Docker, and Podman through `podman-docker`. The change edits one mount option and builds no code, so it has no build cost.

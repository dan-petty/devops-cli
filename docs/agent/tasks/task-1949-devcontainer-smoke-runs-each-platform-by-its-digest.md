# Task: The DevContainer Smoke Test Runs Each Platform by Its Own Manifest Digest (#1949)

**Issue**: [#1949](https://github.com/dan-petty/devops-cli/issues/1949)
**Scope**: scope/ci
**Feasibility**: I read the failed logs of runs 39896894272 (release pull request #1947, head f98ccd15) and 39893000196 (head 50c9727b). Both stop in `.github/actions/devcontainer-smoke` with `docker: cannot overwrite digest` after `docker run` pulls the second platform. The workstation runs rootless Podman, which has no classic image store, so I cannot reproduce the error here. A `workflow_dispatch` run of `ci.yml` on this branch runs the DevContainer Image job and is the proof.

## Description

`devcontainer up` starts `<repository>@<index digest>` and pulls the platform of the runner. The loop then ran `docker run --platform "$PLATFORM" "$REF"` for `linux/amd64` and `linux/arm64` on the same index digest. The classic image store of the Docker on the runner keeps one image for each `repository@digest` reference. The `linux/arm64` pull maps that reference to a second image, and Docker refuses it with exit code 125.

- **The index.** The step reads the image index once with `docker buildx imagetools inspect --raw "$REF"`.
- **The platform digest.** For each platform, `jq -er` selects the first manifest whose `platform.os` and `platform.architecture` match. The attestation manifests have the platform `unknown/unknown`, so they never match. A platform that the index does not hold gives exit code 4, and `set -e` stops the step.
- **The run.** `docker run` starts `${REF%@*}@$DIGEST`. Each platform has its own reference, so the store holds each image under its own digest.
- **Both callers.** `ci.yml` (the pull request check into `main`) and `release.yml` (the `devcontainer-smoke` job after the merge) call the same action. The fix covers both.

## Existing tools considered

- **`docker buildx imagetools inspect`.** It is part of the Docker on the GitHub runners. It reads the registry with the credentials of `docker login`, and it reads `localhost` over HTTP. The change uses it, with no new dependency.
- **The containerd image store.** It holds every platform of an index under one reference. It needs a change to the daemon configuration and a restart of the Docker on each runner. The digest of each platform is the smaller change.
- **`docker manifest inspect`.** It reads the same index, but it needs `--insecure` for a registry over HTTP. That flag would also apply to `ghcr.io` in `release.yml`.

## Acceptance Criteria

- [x] `test_the_devcontainer_smoke_action_starts_the_pushed_digest_as_vscode` requires the index read and a `docker run` by the digest of each platform. It fails on the base.
- [x] The jq filter selects the digest of `linux/amd64` and `linux/arm64` from an index with an attestation manifest, and it gives exit code 4 for a platform that the index does not hold.
- [x] `uv run devops ci` passes (pre-push hook).
- Pending a person: the DevContainer Image check of the release pull request #1947 passes after this pull request merges.

## Deliverables

- [x] `.github/actions/devcontainer-smoke/action.yml`: the index read and the run by the digest of each platform.
- [x] `tests/test_workflow_contracts.py`: the new contract of the step.
- [x] `CHANGELOG.md`: the entry under `### Fixed` of the `[0.2.39]` section, because the cut already collected the fragments of v0.2.39.
- [x] `docs/agent/tasks/task-1949-devcontainer-smoke-runs-each-platform-by-its-digest.md`.

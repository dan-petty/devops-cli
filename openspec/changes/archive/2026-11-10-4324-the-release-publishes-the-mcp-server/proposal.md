# Proposal: The Release Publishes the MCP Server Image (#4324)

## Why
Deployment `mcp-server` in namespace `devops` has been in `ImagePullBackOff` since it was created (2026-11-09T21:16Z). It names `ghcr.io/dan-petty/devops-cli/mcp-server`, and no workflow pushes that image. `release.yml` pushes `devcontainer`, `service` and `runner`. `ci.yml` job `mcp-server-image` (#3220) builds the target with `push: false`. Image Updater cannot find the package, so it writes no digest for it. Closes #4324.

## What Changes
- Add job `mcp-server-image` to `release.yml`. It follows job `runner-image`: build and load the `mcp-server` target, run the smoke test, scan, push by digest, attest, and tag with the release tag and `latest`.
- Run in the release the same smoke test and the same Trivy scan (with `.trivyignore-mcp-server`) as `ci.yml` job `mcp-server-image`. A test fails when the two differ.
- Add a test that fails when a manifest or an ImageUpdater under `k8s/` names `ghcr.io/dan-petty/devops-cli/<name>` and no job of `release.yml` attests `<name>`.
- Update `RELEASE_CYCLE.md` and `k8s/README.md` to list the new job and the person step.

The manifest `k8s/devops/mcp-server/deployment.yaml` does not change: it names the image with no tag, as the `service` and `runner` manifests do, and the entry `mcp-server` of the ImageUpdater already keeps the digest.

## Capabilities

### Modified Capabilities
- `mcp-server-image`: the release publishes the image, and a test ties each image of this repository in `k8s/` to a publish job.

## Impact
- `.github/workflows/release.yml` gains one job that runs only in the run that creates a release. No pull request check changes.
- A person makes the new GHCR package public once, after its first publish. Until then the pod cannot pull the image.
- The pod becomes Ready only after the first release that holds this job.

## Feasibility
Checked against the real system on 2026-11-10:
- `kubectl -n devops describe pod -l app.kubernetes.io/name=mcp-server`: `Back-off pulling image "ghcr.io/dan-petty/devops-cli/mcp-server"` (1296 times in 4h58m). Application `devops` is `Synced` and `Degraded`.
- `devops gh api /user/packages/container/devops-cli%2Fmcp-server/versions` returns 404, `Package not found`.
- The log of the Image Updater controller, every two minutes: `Could not get tags from registry: Get "https://ghcr.io/v2/dan-petty/devops-cli/mcp-server/tags/list": denied`. `spec.source.kustomize.images` of Application `devops` holds `service` and `runner` only.
- `release.yml` has no job that names `mcp-server`. `rg mcp-server .github/workflows` finds `ci.yml` only.
- `Dockerfile` stage `mcp-server` exists and `ci.yml` builds, smoke-tests and scans it on each pull request, so the release can reuse that gate.
- The deployment is wanted: #3220 added the image, #4182 deferred the manifests until the image existed, and #4275 added the manifests with the ImageUpdater entry. Nothing in them publishes the image. So the fix is the publish job, not a removal of the Deployment.

## Existing Tool Considered
The job uses the actions that the `service` and `runner` jobs already use (`docker/build-push-action`, `docker/metadata-action`, `aquasecurity/trivy-action`, `actions/attest-build-provenance`, `docker buildx imagetools`). A reusable workflow would remove the duplicate of the three image jobs, but it changes the pinned `service` and `runner` jobs, which is outside this issue. The cost of this job is one copy of 124 lines, about 15k tokens, which the test of the identical smoke test and scan keeps in step with `ci.yml`.

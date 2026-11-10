# Design

## Decisions
- **Copy the `runner-image` job.** It builds, scans, pushes by digest, attests, then tags. A tag never names an unattested image, and a failed attestation is retried by a re-run. The job needs `release-please` and runs only when `release_created` is `true`, like the other publish jobs.
- **One gate for CI and release.** The smoke test of the release equals the smoke test of `ci.yml`, and the release scan equals the CI scan, including `.trivyignore-mcp-server`. A test compares them. The image that is pushed passed what the pull request checked.
- **Tie the manifests to the publish jobs with a test.** The test reads each YAML file under `k8s/`, collects every value of the keys `image` and `imageName` that starts with `ghcr.io/dan-petty/devops-cli/`, and requires that a job of `release.yml` attests that name. It reads files only, so it needs no network and runs in the devcontainer and on the GitHub runner.
- **Keep the manifest.** The manifest follows the pin convention of the repository: no tag, and Image Updater writes the digest from `latest`. No digest in git can exist before a first publish.

## Rejected alternatives
- **Delete or disable Deployment `mcp-server`.** The roadmap Service and the runner Jobs need the server (#3221, #4191), and Argo CD would prune a deleted manifest. The image is the missing part.
- **Publish the image from `ci.yml` on `main`.** The other images publish at a release only, and a push on each merge would give the cluster an image that is not a release.
- **A reusable workflow for the three image jobs.** It is a larger change of pinned jobs and outside this issue.

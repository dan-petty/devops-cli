# Design

## Decisions

- **One called workflow, one matrix.** `release.yml` calls `release-image.yml` from one job with a matrix over the three images and `fail-fast: false`. Each leg is one call with its own `Build`, `Verify` and `Attest & Tag` jobs, so `needs` and the job outputs stay inside one image, and a failed job of one image stops no job of another image.
- **Verify can write only code scanning.** The issue asked for `contents: read` and `packages: read` only. The image scan action of #6405 uploads its SARIF, so `Verify` also gets `security-events: write`. It can write no package, and it gets no OIDC token, so it can neither tag nor attest.
- **The cache filters of `main` stay.** The issue asked for `runner` and `runner,mcp-server`. The runner stage runs no `apt-get upgrade` since #4361, and the `mcp-server` stage builds on `service-deps`, not on `runner`. So the filters stay `service`, none and `mcp-server`, which are the stages that run `apt-get upgrade`.
- **The smoke steps stay in the workflow until #1858.** `Verify` runs the smoke step of its image with the same text as `ci.yml`. The step condition `inputs.image` selects the step. #1858 replaces the three steps with its image-smoke action.
- **`actions/attest` for the three images.** `actions/attest-build-provenance` v4 only calls `actions/attest`. The devcontainer job keeps its step, because the issue covers the three images of `./Dockerfile`.
- **Re-run the `Build` job for a new package.** A re-run of `Build` also re-runs `Verify` and `Attest & Tag` of that image, and the other jobs keep their outputs, the release tag included.
- **The revision label comes from the input.** The workflow context of `docker/metadata-action` gives the commit of the push that started the run, which can be a later commit than the release commit. A label `org.opencontainers.image.revision` with the input `sha` replaces the default label.
- **The service build names its target.** The release builds `target: service`, which is the last stage, so the build is the same as a build with no target.

## Rejected alternatives

- **Three matrix jobs in `release.yml` (the text of the issue).** A job that needs a matrix job waits for all legs and is skipped when one leg fails. One failed `Verify` would then skip `Attest & Tag` of all three images, which breaks the owner decision that each image promotes on its own. A matrix job also gives only the outputs of its last leg, so the digest of each image would need an output key for each image.
- **Nine jobs, three for each image, as the devcontainer flow.** They promote each image on its own, but they hold the same steps three times.
- **Re-run all jobs for a new package (the text of the issue).** release-please runs again and finds no merged pull request with the label `autorelease: pending`, so it creates no release, and each image job skips.
- **Re-run failed jobs for a new package.** It re-runs only `Verify`, which pulls and scans the same digest again.
- **`context: git` of `docker/metadata-action` (the text of the issue).** The checkout of the release commit has a detached HEAD with no branch and no tag, so the git context throws `Cannot infer ref from detached HEAD` and the Build job of each image fails.
- **A cleanup step for a digest that fails Verify.** Image Updater reads only `latest`, so that digest reaches no cluster. The retention job of #4816 removes untagged digests; a cleanup here would need more write scope.
- **A new test of the values of the new jobs.** docs/TESTING.md forbids a test that asserts a value of a config file. actionlint, zizmor and the log of the first release prove the change.

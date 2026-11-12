# Proposal: #4642

## Why
Each of the 6 Service Image Tests shards builds the `service` stage of the `Dockerfile` again. In 90 shard jobs of 15 successful runs (2026-11-12), the Buildx setup, the build and their post steps took 100.5 s of each shard on average (57 to 129 s), and the mean shard took 298.7 s (measured). Each shard also restores a tooling cache that it does not use, and prints no reason for a skipped test. Closes #4642.

## What Changes
- A new job, `Service Image Build`, builds the `service` stage once with `outputs: type=docker,dest=<archive>` and uploads the archive with `actions/upload-artifact` (retention 1 day, no compression).
- Each shard needs that job, gets the archive with `actions/download-artifact` and runs `docker load`. No shard has a build step.
- The build step sets `DOCKER_BUILD_RECORD_UPLOAD: "false"`. Its post step then uploads no build record.
- The shards run `pytest` with `-rs` and `--durations=10`.
- `setup-toolchain` skips its tooling cache step when `tooling-cache-paths` is empty, and the shards pass an empty value.
- The #1643 invariant accepts the image that a needed job exports and the shard loads, and fails when a shard builds the image again.
- `docs/SDLC.md` states the build job.

## Capabilities
- Modified: `ci-service-image-tests`.

## Impact
- One build of the `service` stage per Service Image Tests run (from 6). The `Service Image` job of `ci.yml` is a different workflow and does not change.
- Each shard starts after the build job, so the run takes about the time of one build longer before the shards start. The runner time of the run falls.
- The shards now depend on the artifact service of GitHub. When it fails, the build job fails and no shard runs.
- The jobs are not required checks, so no ruleset changes.

## Feasibility
- The audit item assumed that the `Service Image` job of `ci.yml` shares the image. Since #4644, the shards are in `service-image-test.yml`, which also runs on the schedule, where `ci.yml` builds no image. An artifact is visible only inside its own workflow run, so the build job is in `service-image-test.yml`.
- The Docker guide "Share built image between jobs with GitHub Actions" documents this pattern: `outputs: type=docker,dest=${{ runner.temp }}/myimage.tar`, then `actions/upload-artifact`, then `actions/download-artifact` and `docker load --input` in the job that needs it. The Docker exporter supports one platform only; the image has one platform.
- The Docker guide "Build summary" documents `DOCKER_BUILD_RECORD_UPLOAD: false`: the summary stays, with no build record archive.
- The log of job 130798014334 (run 43093341637) shows the 631 s post step of the issue comment: the build record upload got an HTML answer from the artifact service 5 times, about 2 minutes each.
- `actions/cache` requires `path`. An explicit empty input counts as given and does not take the default (github/docs #31513, actions/runner #2907), so the step condition `inputs.tooling-cache-paths != ''` sees the empty value.
- The comment "the shards stay under 300 s" of the audit is gone from `ci.yml` since #4644 and #4677. The timeout comment of the shard job named the build time before the test step, so it changes.

## Existing Tool Considered
`docker/build-push-action` with the `docker` exporter, `actions/upload-artifact`, `actions/download-artifact` and `docker load`. All are pinned in the repository already. No new tool.

# Design

## Decisions
- The build job writes the archive with the `outputs` input of `docker/build-push-action`, not with `load` and `docker save`. The Docker guide uses this form, and the job does not need the image in its own Docker engine.
- The upload uses `compression-level: 0`. BuildKit compresses each layer with gzip, so a second compression costs time and saves little.
- The artifact lives 1 day. The shards of the same run read it some minutes after the upload.
- The build job does not set up uv. It needs only the checkout and Buildx.
- The build job keeps `no-cache-filters: service` and `cache-from: type=gha`, as the shards had them. It writes no cache, as the shards did not.
- The build step turns off the build record upload. The build job now holds all six shards, so a slow post step would hold all of them.
- The shard job keeps the release pull request skip term in its own `if`, because the invariant of #4637 reads each job. A skipped build job also skips the shards.
- The shard job keeps its limits (20 min for the job, 14 min for the test step). The job-timeouts item sets them from new measurements.
- The build job limit is 8 minutes: about two times the longest build steps of a shard (129 s) plus the export and the upload.

## Rejected alternatives
- The `Service Image` job of `ci.yml` uploads the image for the shards: the shards are in another workflow since #4644, an artifact is visible only in its own run, and the daily run starts no `ci.yml` image job.
- A registry on the runner or a push to GHCR: it adds a service or a write token for a test image. An artifact needs neither.
- `workflow_run` from `ci.yml`: it starts the suite only after all of `ci.yml`, and it does not apply to the daily run.

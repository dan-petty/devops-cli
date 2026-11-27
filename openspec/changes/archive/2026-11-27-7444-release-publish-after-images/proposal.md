# Proposal: #7444

## Why

The `Release` run publishes a release before its images exist (#7444). The job `Upload Release Assets` needs only `Release Please`, so it publishes the draft about 50 seconds after its creation. The image jobs tag their images up to 6 minutes later.

On 2026-11-27, dan-petty/homelab#572 moved the git pins of devops-cli to v0.226.1. The images of v0.226.1 were not in GHCR yet, and `make k8s-parity` failed (dan-petty/homelab#576).

The owner decided on 2026-11-27 to publish last, after each artifact that the release names exists. Owner decision 1 of 2026-11-12 on #5249 gives the same order: a last job publishes the release after the assets and the images.

## What Changes

- The job `assets` (`Upload Release Assets`) of `.github/workflows/release.yml` needs `release-please`, `image`, `devcontainer-image` and `devcontainer`. Its condition keeps no status function, so GitHub adds `success()`: a failed or skipped image job skips the job, and the release stays a draft. `devcontainer` needs `devcontainer-smoke`, so the smoke test also gates the publication.
- "Re-run failed jobs" runs the failed jobs and the jobs that need them, so the re-run publishes the release when the failed jobs pass.
- The job keeps its name, its step and its permission `contents: write`. No job gets a new permission.
- `RELEASE_CYCLE.md`, `docs/SDLC.md` and the comments of `release.yml` and `release-image.yml` state the new order. The table of `RELEASE_CYCLE.md` gets the row of the uv-seed image, which the job also waits for.
- The order of publication is observable to a consumer of the releases, so the change adds a requirement to the capability `release-publication`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `release-publication`: a release is published only after each of its images has the release tag.

## Impact

- Workflow: `.github/workflows/release.yml`, `.github/workflows/release-image.yml` (comment only).
- Documents: `RELEASE_CYCLE.md`, `docs/SDLC.md`.
- No source code and no test change. docs/TESTING.md gives a workflow change no test.
- A release is published about 6 minutes after its creation, when the last image job ends, not after 50 seconds. The `release` `published` webhook and the `Released in <tag>` comments of the roadmap Service come later by the same time.
- A failed image job, for example a `Verify` scan that finds a fixable vulnerability, now keeps the whole release a draft until a re-run passes. Of the last 32 release runs, no image job failed (`devops gh api` of the runs of `release.yml`, 2026-11-27).

## Feasibility

- The order on main: the run 46056357027 of v0.228.3 published the release at 19:24:12Z (`published_at`). Its last image job, `Attest & Tag DevContainer Image`, ended at 19:30:07Z, and `Runner Image / Attest & Tag` at 19:29:40Z. The eight releases before it show the same gap of about 50 seconds between `created_at` and `published_at`.
- GitHub documentation, [Workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax), `jobs.<job_id>.needs`: when a job fails or is skipped, "all jobs that need it are skipped unless the jobs use a conditional expression that causes the job to continue", such as `always()`.
- GitHub documentation, [Re-run workflows and jobs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs): "When you re-run failed jobs or a specific job, GitHub also re-runs the jobs that depend on them." The page says nothing of the jobs of a called workflow.
- The job `image` is a matrix of calls of `release-image.yml` with `fail-fast: false`. A job that needs it waits for each call, and a failed call fails the need.
- Not proved before a real release run: the order on GitHub, and a re-run that publishes a draft after a failed image job.

## Existing Tool Considered

GitHub Actions `needs` covers the need. The change adds three job names to one `needs` list and builds no code. It deletes no internal code: the image grace of the row `release_comments` (`CONST_ROADMAP_RELEASE_IMAGE_GRACE_MINUTES`) stays until a real release proves the new order (Workflow follow-up of the tasks).

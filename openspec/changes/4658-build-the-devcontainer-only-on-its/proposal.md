# Proposal: #4658

## Why
The `DevContainer Image` job of `ci.yml` started on each push to a pull request and tested its paths in a step. Its filter held `src/`, so it built the image on almost every push: in 26 of the last 30 completed pull request runs, for 354 s on average (measured). The image installs the CLI with `--no-deps`, and Static Analysis already builds the package. The account runs at most 20 hosted jobs at one time, so these jobs make the queue of each pull request longer. Owner decision O2 of 2026-11-11: the image builds only on its own inputs, plus the schedule. Closes #4658.

## What Changes
- The job `devcontainer` moves from `ci.yml` to a new workflow, `devcontainer-image.yml`, with its check name `DevContainer Image` and the same build and start steps.
- The workflow runs on the daily schedule, on `workflow_dispatch`, and on a pull request that changes `.devcontainer/**`, `.dockerignore`, `pyproject.toml`, `uv.lock`, `README.md`, `src/devops_cli/tools_lock/**`, the two devcontainer actions or the workflow. The native `paths` filter stops the run before a runner starts.
- The step `Detect Image Content Changes` and the `if:` of each step go.
- The guard `test_image_path_filter_covers_dockerfile_sources` no longer reads the devcontainer job. A new invariant requires the schedule, the manual run, each file that `.devcontainer/Dockerfile` copies other than `src/`, and no run for a change to `src/` only.
- `docs/SDLC.md` and `docs/DEVCONTAINER_USAGE.md` state the new triggers.

## Capabilities
- New: `ci-devcontainer-image`.

## Impact
- A push to a pull request that changes only `src/` starts no DevContainer Image job. Of the last 131 merged pull requests, 102 matched the old filter and 9 match the new one (measured with `git log` on `main`).
- A `src/` change that breaks `devops --version` in the image shows in the next daily run, up to 24 hours after the merge. The release still builds and starts the image before it publishes it.
- The release pull request changes `pyproject.toml`, so it still builds the image, as it does today. #4637 removes the jobs that are not required from the release pull request.
- The check is not required, so no ruleset changes.

## Feasibility
- GitHub documents that `on.pull_request.paths` decides whether the workflow runs at all: when no changed file matches, GitHub starts no run and no job. A step filter starts the job and takes a runner.
- `ci.yml` on `origin/main` holds the job with `if: workflow_dispatch || pull_request` and the step `Detect Image Content Changes`, whose `IMAGE_CONTENT_PATHS` holds `src`.
- The Actions API for the last 30 completed pull request runs of `ci.yml` (2026-11-12) lists one DevContainer Image job in each. 26 ran the build step, and 4 skipped it. 7 of the 30 runs were on the release pull request.
- `.devcontainer/Dockerfile` copies `pyproject.toml`, `uv.lock`, `README.md`, eight files under `src/devops_cli/tools_lock/` and `src/`, and installs the CLI with `uv pip install --no-deps`.
- `service-image-test.yml` (#4644) and the four path checks (#4653) already use this form.

## Existing Tool Considered
GitHub Actions `schedule`, `workflow_dispatch` and the native `paths` filter. No new tool. The invariant matches the `paths` patterns with `glob.translate` of the standard library, as the #4644 invariant does.

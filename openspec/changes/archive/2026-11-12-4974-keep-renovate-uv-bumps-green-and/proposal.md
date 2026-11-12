# Proposal: #4974

## Why
A review of #4952 found two defects in the Renovate configuration (#4974). First, the preset pins the digest of each Dockerfile image, so Renovate writes `ghcr.io/astral-sh/uv:<version>@sha256:<digest>` in `.devcontainer/Dockerfile`, and `test_the_pins_of_the_table_are_the_pins_of_the_dockerfile` then fails, because it requires a space after the version. The `uv` group pull request thus fails `Tests & Coverage`. Second, `docs/SDLC.md` and the spec say that Renovate pushes an open pull request again only on a conflict. Renovate also pushes an open branch when a member of it gets a new release, and `updateNotScheduled` is `true` by default, so it does this on any day. Each push starts about 25 jobs, and the account runs at most 20 jobs at a time.

## What Changes
- `.devcontainer/Dockerfile` pins the uv image to the digest that the service `Dockerfile` already pins (`0.13.6@sha256:af22a52f…`), and the pin test requires `@sha256:` in both Dockerfiles.
- `.github/renovate/base.json` sets `updateNotScheduled: false`: Renovate pushes an open branch only in the schedule of the branch. A Monday group changes only on Monday. A patch (`at any time`) and a security fix (the schedule of `vulnerabilityAlerts` is empty) still come at any time.
- `docs/SDLC.md` and the test docstring say when Renovate pushes an open branch again.

## Capabilities
- `release-concurrency-and-renovate`: the requirement "Renovate updates on a fixed schedule within the CI cap" changes.

## Impact
- Nothing changes on GitHub until the Renovate CronJob of #4905 runs.
- A conflicted Monday group is rebased on the next Monday, or at once when a person ticks the rebase box of the pull request or of the Dependency Dashboard (`rebaseRequested` skips the schedule).
- The devcontainer image changes only in its reference to the uv image: the digest is the digest of the same tag.
- The change fits one pull request.

## Feasibility
- The Renovate 44.235.1 dry run of #4952 gives two updates for the uv image of `.devcontainer/Dockerfile`: a `pinDigest` to `sha256:af22a52f…` in branch `renovate/uv`, and a patch with a new digest in branch `renovate/patch-uv`. Both write `uv:<version>@sha256:<digest>`.
- With `@sha256:af22a52f…` after `uv:0.13.6` in `.devcontainer/Dockerfile`, `uv run pytest tests/roadmap/test_roadmap_runner_tools.py -k pins_of_the_table` failed on `main` (`At index 1 diff: False != True`).
- The registry gives `docker-content-digest: sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0` for `ghcr.io/astral-sh/uv:0.13.6`.
- Renovate 44.235.1 source: `updateNotScheduled` has the default `true` (`dist/config/options/index.js`). `workers/repository/update/branch/index.js` skips an existing branch outside its schedule only when `updateNotScheduled === false && !rebaseRequested`; it creates no new branch outside the schedule in any case. The default of `vulnerabilityAlerts` has `schedule: []` and is mergeable, so an alert branch is always in its schedule.
- `commitHourlyLimit` does not solve the problem: `workers/repository/process/write.js` sets the `HourlyCommits` count once, from the commits of the current clock hour, before it writes the branches of a run, and no commit of the run adds to it. With one run every 2 hours, the count at the start of each run is 0. `prCommitsPerRunLimit` limits the commits of a run, but it is `globalOnly`, so it belongs to the self-hosted configuration of #4905.
- `renovate-config-validator --strict --no-global .github/renovate.json .github/renovate/base.json` from `renovate@44.235.1` exits 0.

## Existing Tool Considered
Renovate's own `updateNotScheduled` and `pinDigests` options cover the need. The change adds no code.

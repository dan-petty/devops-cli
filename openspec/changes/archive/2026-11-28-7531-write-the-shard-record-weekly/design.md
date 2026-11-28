# Design

## Decisions

- **A weekly schedule.** The record went stale in 11 days (2026-11-17 to 2026-11-28). The command reads the last 20 push runs of `main`, which `main` makes in less than a day, and the shard artifacts stay for 7 days. A daily pull request gives the owner more merges for a small change of the balance.
- **Two jobs.** The job `record` runs the code of the project with a `GITHUB_TOKEN` that only reads (`contents: read`, `actions: read`). It uploads the record. The job `pull-request` has the `release` environment and the App token, and runs no project code: it checks out the tree, downloads the record and runs `create-pull-request`.
- **The release App opens the pull request.** A pull request that `GITHUB_TOKEN` opens starts no workflow, so the required checks would not run on it. The account has one App for such work (`release.yml`, `release-merge.yml`).
- **A person merges the pull request.** AGENTS.md lets only a person merge, with exceptions for Renovate only. The title type `ci` adds no line to the changelog.
- **One branch, `bot/test-durations`.** `create-pull-request` pushes the same branch each week, so at most one such pull request is open. With `delete-branch`, the action deletes the branch when no open pull request uses it, so a merged or closed week leaves no branch behind.

## Rejected alternatives

- **A job in the daily schedule of `ci.yml`.** That job would need the `release` environment and write permissions in the workflow of the required checks, and a daily pull request. A workflow of its own keeps the App token out of `ci.yml`.
- **`git push` and `gh pr create` in a run step.** zizmor 1.33.1 with `--persona auditor` reports `superfluous-actions` at `.github/workflows/test-durations.yml:103` because `gh` is on the runner. A script would need its own check for no change, its own update of an open pull request and its own commit signature. `create-pull-request` v8.1.3 already does these.
- **One job with the App token.** Then the step that runs `uv sync` and `devops ci durations` would run in a job that holds the `release` environment secret.

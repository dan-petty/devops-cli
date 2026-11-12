# Proposal: test each merge once, on the push to main

## Why

Closes #4639. Each merge into `main` ran the tests two times: on the push to `main` and on the release pull request, which release-please updates after each merge. The next merge cancelled most of both runs. From 2026-11-11 12:01 to 2026-11-12 07:57 UTC, it cancelled 49 of 100 push runs and 52 of 77 release runs, so only 50 of 100 merges got a test run that ended. The test jobs used 27.3 runner-minutes for each merge. The owner decided on 2026-11-11 (O3) to test each merge once, on the push to `main`, and to let the release pull request read that result.

## What Changes

- The concurrency group of a push run of `ci.yml` is its commit. A later merge cancels no push run of `main`, so each merge gets one test run that ends. A new push to a pull request still cancels the run before it.
- On the release pull request of this repository (a head branch that starts with `release-please--` and is in this repository), the test shards do not run. A new job, `Tests on Main`, waits for the push run of the base commit of the pull request and passes only when `Tests & Coverage` of that run passed. The required check `Tests & Coverage` passes on that result, and its coverage steps are skipped, as no shard wrote data.
- ADR 0014 records decision O3, with the evidence and the rejected options. `RELEASE_CYCLE.md` and `docs/SDLC.md` say how the release pull request reads the tests of `main`.
- `devops ci job-time` does not change: it already reads the completed push runs of `main`, which are now the one test run of each merge.
- This change alters a CI workflow and documents only. It changes no command, option, message or manifest, so it has no spec delta (`skip_specs: true`).

## Capabilities

None. The change is a CI workflow and documents.

## Impact

- Test runner time for each merge goes from 27.3 to about 21.5 runner-minutes (model on the measured runs). Test jobs for each merge go from 8.7 to about 6.5.
- Each merge gets one test run that ends (100 of 100 in the model, 50 of 100 before), so a red `main` names the merge that made it red.
- The release pull request shows `Tests & Coverage` as pending until the push run of its base ends, a median of about 6 minutes.
- The trigger of release-please, `release.yml`, the required checks and the repository settings do not change.
- The change fits one pull request.

## Feasibility

- `release-please-config.json` sets `always-update: true`, so release-please bases the release pull request on each new commit of `main`. The head branch of the release pull request #4964 is `release-please--branches--main--components--devops-cli`, in this repository, by the release App.
- The repository is public, so a fork can open a pull request with any branch name. The condition also checks `github.event.pull_request.head.repo.full_name == github.repository`.
- The GitHub REST API lists the runs of a workflow by `event`, `branch` and `head_sha` (`GET /repos/{owner}/{repo}/actions/workflows/{id}/runs`), and the jobs of a run with their conclusion (`GET /repos/{owner}/{repo}/actions/runs/{id}/jobs`). A token with `actions: read` reads both.
- The run times come from the Actions API: 100 push runs and 77 release runs of `ci.yml`, read with `uv run devops gh api` and the GitHub session of `devops`.
- GitHub Actions takes an expression in `concurrency.group`, so the group can hold `github.sha` for a push and `github.ref` for every other event.

## Existing Tool Considered

- GitHub Actions job conditions, the concurrency group and the `gh` CLI that the hosted runner image holds, through the GitHub REST API. The new step is a shell loop of two `gh api` calls, as `release.yml` already uses. No new dependency.
- `lewagon/wait-on-check-action` and `fountainhead/action-wait-for-check` wait for a check name on a commit. A push run and a scheduled run of `main` can hold the same commit, and the scheduled run skips `Tests & Coverage`, so a check name alone can read the wrong run. They also add a third-party action. Rejected.
- The change deletes no internal code.

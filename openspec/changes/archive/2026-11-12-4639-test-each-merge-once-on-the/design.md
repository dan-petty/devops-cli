# Design

## Decisions

- **No merge cancels a push run of `main`.** The concurrency group is `ci-<workflow>-<event>-<sha>` for a push and `ci-<workflow>-<event>-<ref>` for every other event. Each push run ends, so the release pull request reads a run that ends, and each merge has its own result. The issue asked for this choice between "the `main` run completes" and "the release pull request reads the newest completed `main` run".
- **The release pull request reads the run of its base commit.** The job `Tests on Main` reads the push run of `ci.yml` on `main` whose `head_sha` is `github.event.pull_request.base.sha`, the commit of `main` that GitHub merges the pull request into. It polls every 30 seconds until the run ends, then reads the conclusion of the job `Tests & Coverage` of the latest attempt. Any result but `success`, no such job, or no end in 35 minutes fails the job.
- **A separate job holds the wait.** The required job `Tests & Coverage` keeps its name and its limit of 5 minutes. It needs `test-shard` and `main-tests`. Its gate step fails unless the shards passed or `Tests on Main` passed. Its steps that need the data of the shards run only when `needs.test-shard.result == 'success'`.
- **Time limits nest.** Of the 50 push runs that ended, `Tests & Coverage` ended at most 1,078 seconds (18 minutes) after the run started. The wait stops after 35 minutes, the step limit is 37 minutes and the job limit is 40 minutes.
- **Only a branch of this repository is a release branch.** The condition is `startsWith(github.head_ref, 'release-please--') && github.event.pull_request.head.repo.full_name == github.repository`. The contract test holds the condition, and a mutation without the repository check fails it.

## Rejected alternatives

- **Read the newest push run of `main` that ended.** That run can be of an older commit, so a defect of the newest merge does not show on the release pull request before a release.
- **Keep the cancel of push runs and read the run of the base commit.** The model of the measured merges gives about 18 runner-minutes for each merge, against 21.5 with this design. But 49 of 100 merges get no test run that ends, and the release check reads a cancelled run whenever a merge comes while it waits.
- **The wait as a step of `Tests & Coverage`.** The job limit must then be 40 minutes for every pull request, against about two times the 63 seconds of the join. The contract `test_every_job_has_a_limit_and_each_step_limit_is_under_it` needs a whole number, so an expression cannot set two limits.
- **A job of the push run writes the result on the release pull request.** The push run starts before release-please updates the release pull request, so the run does not know the head commit to write on.
- **A wait action from the Marketplace** (`lewagon/wait-on-check-action`, `fountainhead/action-wait-for-check`). They wait for a check name on a commit, and a scheduled run of `main` on the same commit skips `Tests & Coverage`. They also add a third-party action.

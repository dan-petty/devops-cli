# The required checks of `main` gate the merge, and the pre-push hook runs only the fast static checks

ADR 0014 amends [ADR 0004](0004-ci-is-the-authoritative-gate.md). It replaces what ADR 0004 says about the rulesets, the Copilot review and the local runs. ADR 0004 still holds that CI is the authoritative gate, and that the aggregate jobs `Static Analysis` and `Tests & Coverage` are the names that the ruleset reads.

ADR 0004 said that the rulesets require `Static Analysis` and `Tests & Coverage`. Nobody applied that to the rulesets ([#842](https://github.com/dan-petty/devops-cli/issues/842)), so the repository required no check until 2026-10-23. On 2026-10-18, pull requests that were green on their own bases merged into a red release branch. At the same time, every push ran the full `uv run devops ci` in the pre-push hook. That run took minutes on a quiet host and much longer under the load of parallel agents. It ran again after each rebase or amend.

[#1752](https://github.com/dan-petty/devops-cli/issues/1752) asked which checks are required, and whether a merge queue serializes the merges. It also asked what runs locally before a push, and what only the owner can change. The owner answered them on 2026-10-22. This ADR records those answers.

## Decision

- **Required checks.** The `main` ruleset requires `Static Analysis`, `Tests & Coverage` and `Semantic PR title`, as [ADR 0012](0012-releases-are-derived-by-release-please-from-trunk-and-milestones-are-planning-buckets.md) decision 10 says. Every topic pull request targets `main` ([ADR 0013](0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md)), so these checks gate every merge. The release pull request shows the same three checks, and its `Tests & Coverage` reads the test run of `main` (see **One test run per merge**).
- **No strict policy, and no merge queue.** The ruleset does not require a branch to hold the current `main` before it merges (`strict_required_status_checks_policy: false`). The owner decided this on 2026-10-24, in place of the 2026-10-22 answer that the strict policy stays. The release pull request shows the required checks of each new `main`, so a defect that two pull requests make together shows in its status before a release. No merge queue serializes the merges.
- **One test run per merge** (amended on 2026-11-12 for [#4639](https://github.com/dan-petty/devops-cli/issues/4639), as the owner decided on 2026-11-11 in decision O3 of the CI audit). Each merge into `main` gets one test run, on the push to `main`.
  - The concurrency group of a push run of `ci.yml` is its commit. A later merge cancels no push run, so each push run ends. A new push to a pull request still cancels the run of the push before it.
  - The release pull request runs no test shard. Its job `Tests on Main` waits for the push run of its base commit, and its `Tests & Coverage` passes only when `Tests & Coverage` of that run passed. `Static Analysis` and `Semantic PR title` run on the release pull request as before.
  - Only a branch of this repository whose name starts with `release-please--` takes this path. The branch of a fork runs the shards.
  - The trigger of release-please, `release.yml` and the required checks do not change. `devops ci job-time` reads the push runs of `main`, so it reads this test run of each merge.
- **Local runs.** The pre-push hook runs only the fast static checks: `ruff` lint and `ruff format`. The hook `devops-ci-workflows-pre-push` adds `actionlint` and `zizmor` when a push changes a file in `.github/workflows/` or `.github/actions/` (#3043). The hook `branch-current` runs first and refuses a branch that does not hold `origin/main` (#4670). The full `uv run devops ci` is a manual command. Remote CI is the authoritative gate (ADR 0004).
- **Copilot review.** Copilot reviews a pull request only when a person requests it. No setting requests a review automatically.
- **Cached verdict.** Question 3 asked how a cached verdict of `devops ci` lasts across a rebase that changes nothing in the tree under test ([#1663](https://github.com/dan-petty/devops-cli/issues/1663)). That question applies only to the optional full local run. No push depends on a cached verdict.
- **Owner steps.** Only a person changes the ruleset and the Copilot settings. The steps are: add the three required checks, keep the strict policy off, and turn off the automatic Copilot review.
- **Sequence.** The pre-push hook changes only after the required checks of `main` gate every topic pull request. That condition became true on 2026-10-23. [#2110](https://github.com/dan-petty/devops-cli/issues/2110) changes the hook.

## Evidence

- **The full local run, from #1752 (2026-10-20).** It took 2.5 minutes on a quiet host and 7 to 15 minutes under the load of parallel agents. Under load that day, pre-push runs took 9 to 15 minutes each. One failed on a timeout, and its rerun passed.
- **The full local run, from #2110 (2026-10-24).** The data is the CI cache entries of the 75 passing runs of the last 24 hours. The host has 16 CPUs and runs several agents at once.
  - The sum of the check durations had a median of 23 minutes, a p90 of 39 minutes and a maximum of 70 minutes. The checks run in parallel. `test` alone had a median of 7.2 minutes (maximum 24), and `security` a median of 5.9 minutes (maximum 28).
  - Nothing limits how many runs share the host, and the pytest of each run uses every CPU. The load average reached 88.
  - The cache cannot help a push, because every push follows a rebase or an amend, and the content is then new. In 7 days, 1 of 186 passing runs verified content that another worktree had already verified.
  - Under that load, tests that wait for a time window fail ([#2069](https://github.com/dan-petty/devops-cli/issues/2069), [#2092](https://github.com/dan-petty/devops-cli/issues/2092)), and the whole run starts again.
- **The required checks in CI (2026-10-24).** The data is the jobs of the 25 latest passing pull request runs of `ci.yml`, from 09:41 to 14:22 UTC.
  - `Static Analysis` took a median of 105 seconds (maximum 119). `Tests & Coverage` took a median of 291 seconds (maximum 307).
  - Each job waited at most 4 seconds for a runner. The whole run, with the jobs that are not required, took a median of 314 seconds.
  - The jobs run on GitHub-hosted runners, so the load of the local host does not change these times.
- **What the required checks run.** `Static Analysis` runs `uv run devops ci --check --no-cache --skip test,outdated`. `Tests & Coverage` runs `uv run devops ci --check --no-cache --only test`. Since #3050 it runs that row in four shard jobs, `uv run devops ci --check --no-cache --only test --shard <n> --shards 4`, and the job `Tests & Coverage` joins their coverage data, so the required name stays on one job. Together they run every check of `devops ci` but `outdated`. The scheduled `Dependency Freshness` job runs `outdated`.
- **The ruleset (2026-10-24).** `devops gh api repos/dan-petty/devops-cli/rulesets` lists one ruleset, `main`. Its last change was on 2026-10-23 at 18:49 UTC.
  - It requires `Static Analysis`, `Tests & Coverage` and `Semantic PR title`. It has no bypass actor.
  - It has no `merge_queue` rule and no `copilot_code_review` rule.
  - Its `strict_required_status_checks_policy` is `false`. ADR 0012 read the policy as on, with an empty list of checks, on 2026-10-22. On 2026-10-24 the owner said that the policy stays off, because the status of the release pull request shows a defect on `main`.
- **The merge queue.** GitHub announced the merge queue for "private and public repos on the GitHub Enterprise Cloud plan" "and all public repos owned by organizations" ([changelog, 2023-07-12](https://github.blog/changelog/2023-07-12-pull-request-merge-queue-is-now-generally-available/)). A user account owns this repository.
- **One test run per merge (2026-11-12, #4639).** The data is the 100 push runs of `ci.yml` on `main` from 2026-11-11 12:01 to 2026-11-12 07:57 UTC, and the 77 runs of the release pull request in the same time, read from the Actions API.
  - The next merge cancelled 49 of the 100 push runs and 52 of the 77 release runs. Only 50 of the 100 merges got a test run that ended.
  - The test jobs, the four shards and their join, used 1,498 runner-minutes on `main` and 1,230 on the release pull request: 27.3 runner-minutes for each merge.
  - A push run that ended used 18.2 runner-minutes of test jobs (mean of 50 runs). Its `Tests & Coverage` ended a median of 367 seconds and at most 1,078 seconds after the run started.
  - A model of the same merges with this rule gives 1,818 runner-minutes on `main` and 328 for `Tests on Main` and the join on the release pull request: 21.5 runner-minutes for each merge. Each of the 100 merges gets a test run that ends.
  - `release-please-config.json` sets `always-update: true`, so release-please bases the release pull request on each new commit of `main`. The release pull request changes only `.release-please-manifest.json`, `CHANGELOG.md`, `pyproject.toml` and `uv.lock`.
- **The Copilot review.** GitHub can turn on an automatic review in three places. They are a personal Copilot setting for the pull requests of that person, a repository ruleset rule and an organization ruleset rule. The `main` ruleset has no such rule, and no organization owns the repository. The pull requests #2105, #2109 and #2112 have no review.

## Considered Options

- **The full `devops ci` in the pre-push hook (the old state)**: rejected. It costs the times above on each push, and again after each rebase or amend. Only 1 of 186 passing runs in 7 days checked content that another worktree had already verified. Its load makes timed tests fail on the shared host. CI then runs the same checks again.
- **The fast checks plus the changed tests before a push**: rejected. The tests that cover a shared module are a large part of the suite. For `src/devops_cli/config/constants.py`, the selector picks 109 of the 484 test modules ([#2086](https://github.com/dan-petty/devops-cli/issues/2086)). The commit hook runs no tests for the same reason.
- **A merge queue**: not available. A user account owns the repository.
- **The strict policy**: rejected on 2026-10-24. Each merge into `main` puts every other open pull request out of date, and its author updates the branch and the required checks run again. Without it, the merged tree is not always the tested tree, and two pull requests that are green alone can make `main` red, as on a release branch on 2026-10-18. The release pull request shows the required checks of each new `main`, so that defect shows in its status before a release.
- **A test run on the push to `main` and on the release pull request (the state before #4639)**: rejected by the owner on 2026-11-11 (O3). Each merge started two test runs, and the next merge cancelled most of both (see Evidence).
- **The release pull request reads the newest push run of `main` that ended**: rejected. That run can be of an older commit, so a defect of the newest merge does not show on the release pull request before a release.
- **Keep the cancel of push runs, and read the run of the base commit**: rejected. The model gives about 18 runner-minutes for each merge, but only half of the merges get a test run that ends. A red `main` then does not name the merge that made it red, and the release pull request reads a cancelled run when a merge comes while it waits.
- **A job of the push run that writes the result on the release pull request**: rejected. The push run starts before release-please updates the release pull request, so the run does not know the head commit to write on.
- **A cached verdict that lasts across a rebase, to keep the full run before a push (question 3)**: rejected. The cache cannot help a push, because each push carries new content. The verdict stays useful only to an optional manual run.

## Consequences

- #2110 changes the pre-push hook `devops-ci-pre-push` to the fast static checks. It also changes AGENTS.md rule 5 and every document that says that the hook runs the full `devops ci`.
- An agent loses the full local run before each push. Before, a push carried a local pass of the tests, the coverage, `mypy`, the security scans, the documents check, the lockfile and the build. Now a defect in one of them shows after the push, in a required check of the pull request.
- The required checks cover that loss before the merge.
  - They run every check of `devops ci` but `outdated`, on GitHub-hosted runners that the host load does not slow.
  - The ruleset blocks the merge while a required check fails or has not run.
  - An agent reads the result with `devops pr monitor <pr_number>`. It marks the pull request ready only after the checks pass (AGENTS.md rule 6).
- A defect that the full local run found now costs a second push and a CI run of about 5 minutes. The agent waits for CI, not for its host.
- CI runs `--check`, so it fixes nothing. A lint or format problem that the local run fixed now fails `Static Analysis`, unless the fast pre-push checks find it first. Generated documents that are out of date fail `Static Analysis` too. The author regenerates them with `devops docs generate --sync-readme` when a command or an option changes.
- The full `uv run devops ci`, or one check of it with `--only`, stays available by hand. Its cached verdict matters only to that manual run.
- With no strict policy, a merge does not put the other open pull requests out of date. Two pull requests that are green alone can still make `main` red together. The release pull request then shows the red check before a release, and the fix goes in as a new pull request. An author who gets a merge conflict rebases the branch.
- ADR 0004 gets a first line that names this ADR.
- Each merge costs one full test run on `main`, as no merge cancels it. In a burst of merges, these runs wait for runners: three merges in one minute start 15 test jobs, and the account runs at most 20 jobs at one time.
- `Tests & Coverage` of the release pull request is pending until the push run of its base ends, a median of about 6 minutes after the merge. It fails when a person cancels that run, or when the run does not end in 35 minutes. A person then runs the failed job again.
- The release pull request does not test its own version lines. `Static Analysis` checks the lockfile and the build on it, and `release.yml` builds, starts and scans each image before it publishes the image.

- Pending a person: make sure that the personal Copilot setting "Automatic Copilot code review" is off. No API reads it.

## Revisit Conditions

- GitHub offers a merge queue to this repository.
- A defect that the full local run finds gets past the required checks and reaches `main`.
- A defect that two pull requests make together reaches a release, because the release pull request did not show it.
- The queue time that `devops ci job-time` prints for the push runs of `main` grows after #4639, because no merge cancels a push run.

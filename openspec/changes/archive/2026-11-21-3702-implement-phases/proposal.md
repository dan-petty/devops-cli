# Proposal: #3702

## Why

The implement Job runs the agent shell in the runner container, next to the App private key (#2695). Part B (#6601) put fix-checks on the phases `prepare`, `agent` and `publish`, and #6655 made them plain git. This change puts implement on the same phases, on a plain issue-branch flow that the owner chose (#3702 comment 7065393209). Closes #3702.

## What Changes

- `devops roadmap implement --confirm` takes `--phase prepare|agent|publish|all` and `--work`. `all` runs the three phases in one process, so the Job template stays as it is until #3700.
- `prepare` checks the claim, clones into the run folder, switches to the issue branch, sets Status In Progress, and records the base and the lease.
- `agent` rebases onto the base and settles each stop as a developer does, runs the groups, the documents, the archive and the scoped checks, and writes `work.patch`, `archive.patch` and `outcome.json`. It makes no GitHub call and no longer calls `fix_rebase_conflict`.
- `publish` reads the outputs as data, checks the claim, applies the patches in a new repository as commits of the bot, pushes with a lease, and opens or updates the draft. It writes the comments, the record and the Status of the outcome.
- No run pushes before `publish`: the checkpoints, the withdraw, the rebase before each push and `implement.base` go.

## Capabilities

- `roadmap-implement-job`: the run on the phases; no checkpoint and no withdraw.
- `roadmap-item-claim`: the claim checks of the phases.
- `roadmap-implement-runner`: the trust zones of the phases.

## Impact

A drafted branch holds two commits of the bot on the default branch: the work and the archive. The pull request is squash-merged, so the merge does not change. A killed Job loses the groups of its run. `devops roadmap follow` shows no live trace while the agent runs.

## Feasibility

`git apply --index`, `git push --force-with-lease=<ref>:<sha>` with a lease that the repository does not hold, and an empty lease for a new branch work on git 2.55 (probes of the git audit). The end-to-end tests of the implement Job run on real git.

## Existing Tool Considered

`pydantic-ai-harness` runs the agent (in use). Git porcelain applies and pushes the patch; no library covers the trust split of one Job. Cost: about 5,000 changed lines, of which about 1,000 are moves and 700 are deleted tests.

# Proposal: #6601

## Why

The fix-checks Job runs the agent shell in the runner container, next to the App private key (#2695). The parent item #3702 splits a run into three trust zones. Closes #6601, part B of #3702: it adds the phases and runs fix-checks on them as the pilot.

## What Changes

- New package `roadmap/phases`: the run folder (`state/`, `work/`, `out/`), the read of an agent output as data, the patch of the agent phase in a new git folder, and `publish_patch`, which #6528 uses for stage.
- `devops roadmap step fix-checks --confirm` takes `--phase prepare|agent|publish|all` and `--work`. `all` runs the three phases in one process, so the Job template stays as it is until #3700.
- `prepare` judges the round with no agent code, clones into `work/` and leaves no credential there, and records the workflow files that the merged plan names.
- `agent` runs tier 1, the scope check and the model fix (`run_fix_step`, as before), and makes no GitHub call.
- `publish` reads the outputs as data, checks the claim, applies the patch with `git apply --cached`, writes one commit of the bot, checks the claim again and pushes with a lease on the judged head.

## Capabilities

- `roadmap-phases` (new): the run folder, the patch and the publish.
- `roadmap-fix-checks`: the repair runs on the phases.

## Impact

The fix-checks Job runs the same round, and its result line does not change. The commit of a repair is one commit of the bot: the fixers' own commits stay in the agent clone. The comment that names the files puts them in a fenced block. The hand-off rules of part A (#6559) do not change.

## Feasibility

`git apply --cached`, `git write-tree`, `git commit-tree` and `git diff-tree --raw` exist in git 2.x. `OriginGit` already runs each network call in a new git folder. The end-to-end tests of the repair run on real git.

## Existing Tool Considered

The parent item names the pattern of GitHub Agentic Workflows safe outputs, Codex cloud and the Copilot cloud agent. Git plumbing applies the patch; no library covers the trust split of one Job. Cost: about 1500 changed lines.

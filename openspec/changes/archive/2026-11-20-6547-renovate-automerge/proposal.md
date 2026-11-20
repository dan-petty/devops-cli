# Proposal: #6547

## Why
Owner, 2026-11-20: "I would like to auto merge all minor and bugfix renovate PRs". The shared preset `.github/renovate/base.json` turns on no automerge, and only the security fixes of devops-cli merge themselves (#6031). A person merges each other update of the four repositories that extend the preset: devops-cli, devtools, devcontainer-features and vibes. Closes #6547.

## What Changes
- The shared preset gets one package rule: the update types `minor`, `patch` and `digest` get `automerge: true`, `automergeType: pr` and `platformAutomerge: false`. Renovate merges such a pull request itself, on a later run, only when each check of the pull request passed.
- The requirement of #6031 no longer forbids automerge in the shared preset. The security fixes of devops-cli keep GitHub auto-merge.
- `AGENTS.md` names the second exception to "only a person merges pull requests"; `docs/SDLC.md`, `docs/CLUSTER.md` and the description in `.github/renovate.json` say the same.

## Capabilities
- `renovate-service`: one modified requirement, one new requirement.

## Impact
- Minor, patch and digest updates merge with no person in the four repositories. Each one releases through the normal release flow of its repository.
- A group branch merges only when each update in it can merge, so a group that holds a major update waits for a person.
- A pull request with a failing, pending, cancelled or timed-out check, or with no check, does not merge.

## Feasibility
Renovate 44.239.2, the release that CronJob `renovate` runs, read on 2026-11-20:
- `lib/workers/repository/update/pr/automerge.ts:93`: Renovate merges a pull request only when the branch status is `green`.
- `lib/modules/platform/github/index.ts:1296-1321`: the status is `green` only when each check run ends `success`, `neutral` or `skipped` and the commit statuses pass; with no check run and no commit status, it is `yellow`.
- `lib/workers/repository/updates/generate.ts:480`: a branch automerges only when each update in it has `automerge`.
- `lib/workers/repository/init/vulnerability.ts:164-171`: the `vulnerabilityAlerts` rules come after the package rules, so the GitHub auto-merge of the security fixes of devops-cli stays.

GitHub auto-merge waits only for the required checks of a ruleset. devtools has no ruleset, and the ruleset of vibes requires no check (2026-11-20). So the rule uses the automerge of Renovate, not GitHub auto-merge.

## Existing Tool Considered
Renovate automerge (`automerge`, `automergeType`, `platformAutomerge`). No code.

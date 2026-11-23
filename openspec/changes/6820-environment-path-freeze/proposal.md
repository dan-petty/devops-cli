# Proposal: #6820

## Why
Closes #6820. Step 12 of `docs/HOMELAB_REPO_SWITCH.md`, the plan of #5134. On 2026-11-23 at 00:08 UTC, step 11 switched Argo CD to dan-petty/homelab: `bootstrap`, `cluster` and each child Application read the copy of the environment in homelab. Only Application `devops` (`k8s/devops`) and the rules value file of Application `prometheus` still read devops-cli. A devops-cli pull request that changes an environment path now changes nothing live, but its author can think that it deploys. The copy in homelab and the files in devops-cli then drift apart before step 17 deletes the files. Renovate of devops-cli also updates the image pins in the environment paths: #6817 merged at 00:29 UTC, after the switch, and changed 11 environment files. The GitOps section of `k8s/README.md` still says that Argo CD reads the environment from devops-cli.

## What Changes
- A new check of the `k8s` row of `devops ci`, `tests/gate/k8s_checks/environment_freeze.py`, refuses a branch that changes an environment path. An environment path is a file of `k8s` outside the product folders `k8s/devops` and `k8s/overlays/homelab/devops`: the pathspec of step 10 of the runbook. A Markdown file deploys nothing, so the check does not refuse it. The check reads the changed paths from `git diff --name-only --no-renames` between the merge base with `origin/main` and `HEAD`, so a new, a changed and a deleted file count. Each finding names the path and dan-petty/homelab. `Static Analysis` runs the `k8s` row, so the check is required.
- A package rule of `.github/renovate.json` turns off the updates of each dependency of an environment path. Homelab Renovate updates its copy.
- `k8s/README.md` (the introduction, GitOps, Bootstrap & Adoption and Recovery) and `docs/CLUSTER.md` say that Argo CD reads the environment from dan-petty/homelab and the product base from this repository. Bootstrap and Recovery take the bootstrap file and the values of Argo CD from a homelab checkout.
- Step 12 of the runbook names the check and the Renovate rule. Step 17 deletes both with the environment files.
- The check and the Renovate rule change what a pull request author and Renovate observe, so the change carries spec deltas.
- The change fits one pull request.

## Capabilities
- `ci-gate-rows`: ADDED requirement "The k8s row refuses a change to an environment path".
- `release-concurrency-and-renovate`: ADDED requirement "Renovate updates no environment path of the homelab repository".

## Impact
- A pull request that changes an environment path fails `Static Analysis`. Its author makes the change in a homelab pull request. An open Renovate pull request that changes an environment path fails too, and Renovate opens no new one.
- Renovate still updates the pins of `k8s/devops` and `k8s/overlays/homelab/devops`.
- `devops ci --check --only k8s` needs `origin/main` and its merge base with `HEAD` in the checkout. Each CI job that runs the row checks out the full history.
- A change of the dashboard generator `src/devops_cli/grafana/service_dashboard.py` that changes a committed dashboard of `k8s/monitoring/dashboards/` waits for step 17, or goes to homelab.

## Feasibility
- Runbook: step 10 of `docs/HOMELAB_REPO_SWITCH.md` gives the pathspec `k8s ':(exclude)k8s/devops' ':(exclude)k8s/overlays/homelab/devops'`. Step 12 asks for the check and the README change in one pull request, and step 15 changes `k8s/README.md` in devops-cli again. So the check cannot refuse `k8s/README.md`.
- Set count on origin/main `0a67d9d0d`: `git ls-files -- k8s ':(exclude)k8s/devops' ':(exclude)k8s/overlays/homelab/devops' | wc -l` gives 150 environment files, and the metadata file `k8s/devops-cli-copy.json` of homelab lists 150 paths. 2 of them are Markdown files (`k8s/README.md`, `k8s/llm/profiles/README.md`), and the check allows both, because a document deploys nothing. The other 148 are refused. `git ls-files -- k8s/devops k8s/overlays/homelab/devops | wc -l` gives 54 product files.
- CI: the `Static Analysis` job of `.github/workflows/ci.yml` runs `devops ci --check --no-cache --skip test,outdated,actionlint`, so it runs the `k8s` row, and it checks out with `fetch-depth: 0`, so `origin/main` and the merge base exist. On a pull request, `HEAD` is the merge commit, and `git diff origin/main...HEAD` gives the change of the pull request. On a push to `main`, the diff is empty.
- The fail-to-pass replay runs a gate row in a detached worktree of the merge base, where `origin/main...HEAD` is empty (`src/devops_cli/ci/fail_to_pass.py`, `worktree_add_argv`).
- Renovate 44.239.2 (the image of CronJob `renovate`): `ignorePaths` is not mergeable (`mergeable: false` in `dist/config/options/index.js`), so a repository value replaces the list of `:ignoreModulesAndTests` of `config:recommended`, and it matches by substring or glob with no negation (`dist/workers/repository/extract/file-match.js`). `matchFileNames` of a package rule uses `matchRegexOrGlobList` (`dist/util/string-match.js`): a path matches when a positive pattern matches and no `!` pattern excludes it. The vulnerability rules of Renovate add no `enabled` key (`dist/workers/repository/init/vulnerability.js`), so a security alert does not turn the dependency on again.

## Existing Tool Considered
- git (`git diff --name-only`) gives the changed paths, and the runner of `tests/gate/runner.py` runs the check in the `k8s` row. No open tool refuses the paths of a pull request in this repository. Branch rulesets of GitHub can restrict file paths, but only a person changes the repository settings (AGENTS.md), and a ruleset gives no message that names dan-petty/homelab.
- Renovate covers the ignore with its own `packageRules`, `matchFileNames` and `enabled: false`.
- Build cost: about 60 lines of check code and 8 test cases; about 40k tokens and 1 hour to build, and a low cost to keep, because step 17 deletes the check.
- The change deletes no internal code.

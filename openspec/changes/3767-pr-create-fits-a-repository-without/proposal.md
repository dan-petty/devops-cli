# Proposal: #3767 pr create and pr ready fit a repository without OpenSpec

## Why

Closes #3767. `devops pr create` applies the body rules of devops-cli to every repository. On 2026-11-06 and again on 2026-11-12 an agent opened pull requests in `dan-petty/homelab`, which has no OpenSpec and no CI. The command refused them because the body had no `Closes #<issue>` line and no `Change:` line. It also has no `--head` option, so a checkout of devops-cli cannot open a pull request in another repository. `devops pr ready` refused with "A check runs: no checks reported" until `--force` was given. The agents opened homelab pull requests 19 and 20 with a raw `devops gh api -X POST repos/dan-petty/homelab/pulls`, which skips every check that the command exists to run. Every item of the infra-repo tracker #5120 opens a pull request in homelab.

## What Changes

- `devops pr create` reads `openspec/config.yaml` on the base branch of the target repository (the default branch when there is no `--base`). Where the file is, the body rules stay as they are. Where it is not, the command checks the title only. A read that fails for another reason than a missing file stops the command, as a failed read of the labels file does.
- `devops pr create` gets `--head` (`-H`), which it gives to `gh pr create` and to the REST fallback. Without it, both use the branch of the checkout, as before.
- A dry run reads nothing of GitHub. It takes the switch from the checkout without `--repo`, and does not check the body of another repository.
- `devops pr ready`: when the head commit reports no check run and no commit status, and the repository has no GitHub Actions workflow, no check will start. The command says so, does not judge the checks, prints no warning for the missing checks, and marks the pull request ready with no `--force`. A repository with a workflow still waits (exit 8) while no check is reported.
- `openspec/project.py` gets `repository_uses_openspec`, the read of the same switch for a command that has no clone. `GitHubClient` gets `count_workflows`. `CheckVerdictSummary` gets `reports_nothing`, and the three places that make the pending stand-in for "no checks reported" share one function.
- The help of `pr create` and `pr ready`, the generated command documents, `CONTRIBUTING.md` and the skill `devops-pr-ci` state the rules.

The change fits one pull request.

## Capabilities

- `pull-request-form`: MODIFIED "devops pr create refuses a pull request that breaks the form" and "A dry run checks the form without a request"; ADDED "devops pr create opens a pull request from the branch it is given".
- `pr-merge-readiness`: ADDED "pr ready does not wait for checks in a repository with no CI".

## Impact

- devops-cli keeps every check: its base branch holds `openspec/config.yaml`, and it has 24 workflows, so `pr ready` still waits for the checks to start.
- `devops pr create --repo dan-petty/homelab --head <branch>` opens a draft from the devops-cli checkout. The title check, the labels and the Status of the closed item work as for devops-cli, because homelab has `.github/labels.yml` and a roadmap.
- `devops pr create` makes one more read: the contents of `openspec/config.yaml` on the base branch. `devops pr ready` makes one more read, of the workflow count, only when the head commit reports no check.
- `devops pr check-readiness` and `devops pr monitor` already skip the body rules where the base has no `openspec/changes/`, so they do not change.

## Feasibility

- `devops gh issue view 3767` and its comments (2026-11-12): the refusals of `pr create` ("The body has no line `Closes #<issue>`", "The body has no line `Change:`"), the missing `--head`, and `pr ready` "A check runs: no checks reported".
- `devops gh api repos/dan-petty/homelab` (2026-11-12): private, default branch `main`. `contents/openspec/config.yaml`: HTTP 404. `contents/.github`: `labels.yml` and `roadmap.toml`.
- `devops gh api repos/dan-petty/homelab/actions/workflows`: `total_count` 0. The head commit of homelab pull request 19 (`9b2febd`): 0 check runs; the combined status is `pending` with `total_count` 0, which `read_commit_checks` turns into the pending stand-in "no checks reported".
- `devops gh api repos/dan-petty/homelab/rules/branches/main`: HTTP 403, "Upgrade to GitHub Pro or make this repository public to enable this feature". So the required checks of the rulesets, which the refine design of the issue proposed, cannot be read for a private repository on the free plan.
- `devops gh api repos/dan-petty/devops-cli/actions/workflows`: `total_count` 24. `rules/branches/main` requires `Static Analysis`, `Tests & Coverage` and `Semantic PR title`.
- `src/devops_cli/openspec/project.py` (#4629) names `openspec/config.yaml` as the one switch of OpenSpec for a repository. The stage job and `devops ai agents` read the same file.
- `gh pr create --help` (cli/cli manual): `-H, --head <branch>` names the branch that holds the commits; the default is the current branch.

## Existing Tool Considered

`gh pr create --head` and the GitHub REST API (`GET /repos/{owner}/{repo}/actions/workflows`, contents API) cover the reads and the create request, and the change uses them. No tool decides which body rules of devops-cli apply to a repository, because the rules are in this repository's command. The alternatives check of 2026-11-08 found none. The cost to build is about 150,000 tokens and 1 hour, and about 10,000 tokens a year to keep.

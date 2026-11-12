# Design

## Decisions

- **The switch of the body rules is `openspec/config.yaml` on the base branch of the target repository.** `openspec/project.py` already names this file as the one switch of OpenSpec for a repository (#4629): the stage job holds the items of a repository without it, `devops ai agents` writes the OpenSpec rule into AGENTS.md only where it is, and onboarding adds it (#3770). A repository opts in to the rules of devops-cli when it runs `openspec init`. `pr create` has no clone of the target repository when `--repo` names another one, so `repository_uses_openspec` reads the file through the contents API of the roadmap store. `_form_checked` already reads `.github/labels.yml` of the target on `base` through the same store, so the new read sits beside it and fails the same way.
- **Only a missing file turns the switch off.** `repository_uses_openspec` catches `GitHubFileNotFoundError` only. Any other failure raises, and `pr create` prints it and opens nothing, so a failed read never drops the rules of devops-cli.
- **A repository without OpenSpec gets no body check.** `Closes #<issue>`, `Change:`, the length bounds and the template text are rules of the devops-cli squash commit. The title check stays, because the `type/*` and `scope/*` labels and the Status of the closed item come from it.
- **A dry run takes the switch from the checkout.** A dry run reads nothing of GitHub. Without `--repo` the checkout is the target, so the dry run checks the body when the checkout holds `openspec/config.yaml`. With `--repo` it cannot know the rules, so it checks the title only, as it already skips the scope check.
- **`--head` goes to `gh pr create` and to the REST fallback.** The fallback used the branch of the checkout, which is wrong for a pull request in another repository.
- **No CI means no workflow and no reported check.** `pr ready` waits (exit 8) while the head commit reports no check, because a check can still start after a push. When the commit reports none and `GET /repos/{repo}/actions/workflows` gives `total_count` 0, no check will start. Then `pr ready` says so, gives `draft_readiness` no checks, and drops the pending-check warning. A repository with a workflow keeps the wait, so devops-cli does not change.
- **`reports_nothing` compares with the one stand-in.** `no_checks_reported()` makes the pending item for a commit with no check, and the three places that made it inline call it. `CheckVerdictSummary.reports_nothing` is true when that item is the only one and the read did not fail.

## Rejected alternatives

- **The required checks of the rulesets** (the refine design of the issue). `GET /repos/dan-petty/homelab/rules/branches/main` answers HTTP 403 for a private repository on the free plan. Reading that answer as "no required checks" would match the text of an error. A repository with a workflow and no required check would also be marked ready before its checks start.
- **A setting in `service.repos` or in the infra-repo settings of #5121.** `service.repos` is the configuration of the Service, not of the CLI, and the infra-repo settings are not merged. A setting is a second switch that can disagree with the files of the repository.
- **`openspec/changes/` at the base, as `check-readiness` reads.** `openspec/project.py` names `openspec/config.yaml` as the switch, and the issue names it too. In practice both are present or both are absent.
- **A `--no-openspec` flag.** It adds a manual step, and an agent that forgets it gets the same refusal.
- **Reading `.github/workflows` at the head commit.** The contents read of a directory needs a second store method, and the workflow count is one typed read with the same answer for a repository with no CI.

# Proposal: #6038

## Why
Renovate opened its Dependency Dashboard (#6030) as `dan-petty-renovate[bot]`, and roadmap intake placed it at 20:19Z on 2026-11-16. The dashboard is a tracking issue that Renovate owns and writes again each run, no work item. Renovate also removes each label that it does not set, so intake and Renovate change the labels again every 2 hours. Closes #6038.

## What Changes
- A new setting `roadmap.skip_authors` names the bots whose issues no roadmap row takes. Its code default holds `dan-petty-renovate[bot]`, from `CONST_RENOVATE_GITHUB_APP_SLUG`.
- One shared selection point, `roadmap_issues` in `roadmap/stores/store.py`, leaves out the pull requests and the issues of these bots. `select_items` and `select_candidates` start from it, so every listing of Items and Candidates of both stores skips such an issue. Intake reads its listing through it, so the issue is no candidate and no item to compare with.
- The behavior of the store changes, so the change carries a spec delta.

## Capabilities
- `roadmap-item-labels`: the requirement "An Item is an issue with a priority label" is modified.

## Impact
- Code: `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/intake/intake.py`, the settings and the defaults.
- Rows: intake, retitle, refine, alternatives, stage, implement, open, watch and metrics read issues only through `items`, `open_items`, `backlog`, `item`, `candidates` or the listing of intake. The plan_drift row reads only pull requests.
- After the release, an agent takes the 4 labels of intake off #6030 (the pull request body names the commands).

## Feasibility
- `GET /repos/dan-petty/devops-cli/issues/6030` gives `user.login` `dan-petty-renovate[bot]`, `user.type` `Bot` and `author_association` `NONE`. GitHub keeps `[bot]` for App bots, so no person can have the login.
- The events of #6030: Renovate set `type/chore` and `scope/deps` at 20:15:06Z (the dashboard labels of `.github/renovate/base.json`). The Service App set `status/new`, `value/medium`, `effort/low` and `priority/p2-medium` at 20:19Z. Renovate took those 4 off at 20:35:43Z, and the Service set them again at 20:47Z. The labels of intake are these 4, not `type/chore` and `scope/deps`.
- The body of #6030 holds no record block now: the write of Renovate replaced it.

## Existing Tool Considered
- Renovate can turn the dashboard off (`dependencyDashboard: false`), but the approvals of `dependencyDashboardApproval` need it. GitHub gives the author in the issue listing that the store reads already, so the rule needs no new request. Cost: about 0.3M agent tokens and 2 hours.

# Proposal: #4660

## Why
Closes #4660. ADR 0016 says that a closed issue holds no `status/*` and no `owner/*` label. `src/devops_cli/roadmap/inbox.py` and `src/devops_cli/roadmap/pull_status.py` use this rule. Today only a hand copy of `.github/workflows/clear-status.yml` removes the labels, and row 5 of `devops roadmap onboard` asks for that copy in each repository. 0 of the 6 other repositories hold the file, and dotfiles and homelab have no workflows folder. Owner decision 6 of #4627 (2026-11-11) chose the Service: the Service removes the labels on the `issues.closed` event, and the poll removes the labels that the event did not remove.

## What Changes
- `status_sync.py`, the module of the one Status writer, gets `clear_closed_labels` and `clear_closed_issues`. `clear_closed_labels` reads one issue again and, when it is closed, sends one label removal request (`store.unlabel_issue`) for each `status/*` and each `owner/*` label that it holds. It keeps every other label. `clear_closed_issues` does this for each closed issue of the listing that holds such a label.
- Each round of the row `implement` calls `clear_closed_issues` after its first Status sweep. The trigger `("webhook", "issues", "closed")` already makes the row due (`CONST_ROADMAP_STAGE_BATCH_KEYS`), so an `issues.closed` delivery starts the round that removes the labels. The 7-minute interval of the row is the poll that removes a label that no delivery removed.
- `.github/workflows/clear-status.yml` is deleted, with no shim.
- `devops roadmap onboard` checks six prerequisites. The clear-status row is deleted. Row 5 is `service.repos` and row 6 is the webhook. The command and its dry run read no workflow file.
- The change alters what the Service writes and what `devops roadmap onboard` prints. Both are observable, so the change carries spec deltas.
- The change fits one pull request.

## Capabilities
- `roadmap-item-labels`: MODIFIED requirement "A closed issue holds no Status and no Owner label".
- `roadmap-onboard`: MODIFIED requirements "One row for each prerequisite", "The exit code follows the missing rows" and "The service.repos row is printed".

## Impact
- The Service removes the labels in each repository of `service.repos`, with no file in the repository. The GitHub App already has `issues: write`.
- The first round of the row in each repository removes the labels of the closed issues that hold them now: 125 issues in 5 repositories on 2026-11-22. Each issue costs one read and one removal for each label. The request windows of the App installation hold the rate.
- `devops roadmap onboard` prints six rows. A repository with no `clear-status.yml` passes.
- `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/onboard.md`, `docs/CLUSTER.md` and the docstrings of `inbox.py` and `pull_status.py` name the Service as the remover. ADR 0016 gets a Status History line.

## Feasibility
- Code on origin/main `9dfe03e3e`: `CONST_ROADMAP_STAGE_BATCH_KEYS` (`src/devops_cli/config/constants.py`) holds `("webhook", "issues", "closed")`, and the rows `stage` and `implement` use it. `SCOPED_UPDATES` (`src/devops_cli/roadmap/run.py`) has no `closed` action, so the router sends the delivery as a trigger to each lane (`roadmap_consumer` in `src/devops_cli/server/routes/webhooks.py`).
- `run_implement_round` (`src/devops_cli/roadmap/implement/implement_submit.py`) calls `sync_statuses` before its first early return, and `store.items()` there reads the listing of every issue, open and closed. `store.issues()` reads the same listing, so the clear adds no listing read.
- `GitHubRoadmapStore.unlabel_issue` sends `DELETE repos/<repo>/issues/<n>/labels/<label>`, which removes one label and keeps the others.
- `refuse_own_write` drops a delivery whose sender is the bot of the App, so the `unlabeled` events of the removal start no round.
- Search of 2026-11-22: `is:issue is:closed` with a `status/*` or `owner/*` label gives 125 issues: 63 in vibes, 22 in homelab, 5 each in devops-cli, danielpetty.com and devcontainer-features. The 5 in devops-cli, which has the workflow, are #4395, #4200, #3932, #3671 and #2524: a label that a writer added after the close stays.
- `tests/invariants/test_architectural_invariants.py` lets only `roadmap/status_sync.py` and the stores remove a `status/` label, so the clear goes in `status_sync.py`.

## Existing Tool Considered
- probot/probot (ISC, maintained, last activity 2026-11-18), verdict `partly`. It gives App authentication and the receipt of webhooks, which the Service already has. Its handler and tests are still written, in Node.js, beside the Python router, and it has no reconcile of closed issues that still hold a label.
- `actions-ecosystem/action-remove-labels` and the current `gh issue edit --remove-label` step need a workflow file in each repository, which this change removes.
- Build cost: about 40 lines of code and 6 tests, about 150,000 tokens and 2 hours to build, keep and fix. The change reuses the router, the batch keys, the store and `write_each`.
- The change deletes `.github/workflows/clear-status.yml`, row 5 of `src/devops_cli/roadmap/onboard.py` (`_check_row_5`, `_CLEAR_STATUS_PATH`) and the read of the workflow file in `onboard_requests`.

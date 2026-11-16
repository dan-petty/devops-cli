# Proposal: #6024

## Why
A review of PR #6015, the step `devops roadmap step review` (#5969), found 9 defects. The mode `plan` writes nothing, so nothing is broken now, but items 1 and 2 must be fixed before a person sets `roadmap.review.mode: on`: a judged head skipped the rules, so a later fact was lost; and a discard closed the pull request before the leased delete, so a failed delete left a closed pull request and an item that never went back. Closes #6024.

## What Changes
- The rules run on each call. `review.key` with `review.source` only saves the model call; a rule verdict that the record and the label hold writes nothing again.
- A discard of the model alone labels and comments, and a person decides the close. A discard of a rule checks the shared branch and the withdraw before the first write, records its start (`review.discard`), deletes the branch with a lease, closes the pull request, and returns the item; a call on the closed pull request ends a discard that stopped. The command's delete skips a branch that is gone.
- A branch that holds the work of the other kind (`implement.branch` or `implement.pr` of a plan, `stage.branch` or `stage.pr` of a delivery) is left for a person.
- The watch row holds the ready mark of a green bot pull request with a verdict label other than `verdict/mergeable` (`ready_held`, the labels of both read paths). The step reads the login of the last ready mark and does not take back a person's ready mark.
- The step skips a live `stage.job`, and stops only on `claim_labels`.
- A wait on CI infrastructure logs one line and, with writes, ends after the new setting `roadmap.review.infra_wait_hours` (6) with one comment for a person. An Issue changed verdict records the text it answered (`review.text`), so the updated work of that text is judged.
- The behavior of a command changes, so the change carries a spec delta.

## Capabilities
- `roadmap-pr-review`: two modified requirements (the writes, the guards) and four new ones (the discard of a rule, the ready hold of the watch row, the limit of the infrastructure wait, one Issue changed for one text).

## Impact
- Code: `src/devops_cli/roadmap/steps/review.py`, `review_facts.py`, `steps/watch.py`, `watch_row.py`, `stores/store.py`, the settings and the defaults, `commands/roadmap_step_review.py`.
- The edits of `watch_row.py` and `steps/watch.py` are only the ready hold: the labels in the GraphQL query and in the REST path, and one condition of the READY rule.
- The change fits one pull request. The mode stays `plan`.

## Feasibility
- `fix_plan.py` refuses a plan pull request that is not a draft, so a plan that the watch row marks ready again never gets fix-plan.
- GitHub closes an open pull request when its head branch goes, so after the delete the close and the return must be repeatable from the closed pull request.
- GraphQL gives `ReadyForReviewEvent.actor` in `timelineItems(itemTypes: [READY_FOR_REVIEW_EVENT])`, in the request that the step already sends.
- `claim_labels` (`roadmap/claim.py`) leaves out `owner/service`; the watch row skips `job_holds` or `stage.job` (`watch_row.py`).

## Existing Tool Considered
- No tool changes. The fix reuses `claim_labels`, `job_holds`, `OriginGit.heads` and `OriginGit.push`, `apply_return`, and the GraphQL read of the step. Cost: about 0.3M agent tokens and half a day. The change deletes the close-first discard path.

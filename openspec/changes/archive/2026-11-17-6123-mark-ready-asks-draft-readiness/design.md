# Design

## Decisions
- **The wrapper asks the decision.** `mark_ready` calls `draft_readiness` before `gh pr ready`. The invariant test keeps `gh pr ready` in `steps/ready.py`, so a path that skips the decision cannot exist.
- **The caller gives its draft.** A caller that judged a draft gives that draft, so the pull request is not read twice. A caller with no draft gets `read_ready_draft`: the pull request, the check runs of its head, and `read_draft`, which takes the kind from the record. A record that holds one pull request as the plan and as the delivery gives the kind implement, which reads the change and its tasks.
- **A refusal raises.** `mark_ready` raises `RoadmapImplementError` with the reason, as for a moved head or a failed `gh`. The watch row judges first and logs the reason, so a refused draft does not stop the round of the other pull requests.
- **The watch row judges a refused head once.** It keeps the head in the ledger field `ready_head`, which the ready path of `fix-checks` already uses once for each head. A new head is judged again.
- **The `--force` of a person skips the decision.** `devops pr ready --force` and `devops roadmap step ready --force` are the explicit choice of a person.

## Rejected alternatives
- **Only add `draft_readiness` to the watch row.** The defect is that `mark_ready` let a caller skip the decision; a new caller could skip it again.
- **Always read the draft in `mark_ready`.** `devops pr ready` judges with `declared` set and with no checks for a repository with no workflow (#3767), and the implement job judges the files of its local diff. One read in `mark_ready` cannot give each of these facts, and a second read costs GitHub requests.
- **Classify the pull request as the delivery in `_find_plan_item`.** The watch row would then leave the draft to its implement Job, which had ended for #3771, so the draft would not be marked ready when it is complete.

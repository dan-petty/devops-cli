# Design

## Decisions

- **Publish the evidence in `_ready`, after `draft_readiness` answers ready and before `mark_ready`.**: It is the one transition point, and it already reads the pull request and its checks, so the comment names the head that the job is about to mark.
- **Reuse `publish_pr_evidence` instead of a second renderer.**: `src/devops_cli/github/pr_evidence.py:96:def publish_pr_evidence(` builds the head commit and the check table as one updatable comment, so the job needs no second evidence renderer.
- **Stop the item before `mark_ready` when the publisher fails, with the class `ci_infra`.**: The evidence is a condition of the ready transition: the pull request stays a draft, the item is Blocked, and the one retry of the class posts the evidence on the next run.
- **Answer the pull request read of the test world with the head that its pull fake holds.**: The publisher reads the head from the pull request, and an empty head reads as an unread check, so the world must answer the head for the comment to be written.
- **Cover the delivery pull request of the implement job only.**: The criteria of the item's proposed design name the implement job, and the other places that mark a pull request ready are outside the item.

## Rejected alternatives

- **Build a second evidence renderer in the implement job.**: `src/devops_cli/github/pr_evidence.py:96:def publish_pr_evidence(` already builds the head commit, the check table, the links and the skipped runs as one updatable comment.
- **Run `devops pr evidence` as a subprocess from the job.**: `src/devops_cli/commands/pr.py:487: from devops_cli.github.pr_evidence import EvidenceAction, publish_pr_evidence` shows that the command is a thin caller of the same function, so a subprocess adds a shell call where a function exists.
- **Publish the evidence in `_checks` after the watch.**: `_checks` runs the repair of a failed watch through `_repair_after_push`, which pushes a new head, so evidence posted there can name a head that the repair replaced.
- **Publish the evidence in `execute` before `_ready`.**: It separates the evidence from the readiness decision and repeats the head read that `_ready` makes at `src/devops_cli/roadmap/implement/implement_run.py:2097:mark_ready(self.repo, pull, draft=draft)`.
- **Log the publisher's failure and mark the pull request ready anyway.**: The pull request would leave draft with no evidence comment, which is the defect that the item names.

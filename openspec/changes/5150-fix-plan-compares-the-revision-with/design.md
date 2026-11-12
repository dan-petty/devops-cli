# Design

## Decisions

- **The review of the head is the baseline.** `_Planner.revise` always reviews the plan that passed the checks, with the verifier of the attempt at the commit of the attempt, and returns its open findings as `PlanRevision.before`. `_settle` compares the last review of the revision with that count, so both counts come from the same pass, the same model and the same commit.
- **The comment findings still go to the planner.** The owner direction of #5061 gives the planner the findings of the stage comment. They join the open findings of the review in `problem`, with no repeat of an equal finding. They do not count, because an earlier review at an earlier commit wrote them.
- **A clean review of the head clears the label.** The stage job removes the label when a later review finds no open finding (`docs/roadmap/stage.md`). The step does the same when the review of the head finds none, also when the comment lists one, and makes no plan call.
- **Report both counts.** The result line gets the count `comment`, and the report of the command names it, so a reader sees how far the comment and the review of the head differ.

## Rejected alternatives

- **Keep the comment count and add only the comment findings to the review.** No review gives the count of a list of findings from another run: a review names its own findings, so the count stays a mix of two reviews.
- **Review the head only when the comment is older than a release.** Two reviews of one plan with the same prompt and model, 7 hours and one commit range apart, gave 1 and 2 open findings, so a stored review of the same release is no baseline either.
- **Drop the comment findings.** The owner direction of #5061 asks for them, and the planner gets them at no model cost.
- **Cap the tokens of an attempt.** The run-count bounds already hold an attempt: at most 3 gate returns for each reply, 2 repair rounds and an extension only while the open findings drop (#5066), 2 attempts for each head and 3 revisions for each pull request. A token cap would stop a repair that makes progress, which the owner direction of 2026-11-11 (loosen caps only with a progress-aware extension) rejects.

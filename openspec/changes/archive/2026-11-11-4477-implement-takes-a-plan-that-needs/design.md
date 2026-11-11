# Design

## Decisions

- The judge reads the label from the `PullStatus` that `_pull_reason` reads already. The check needs no new request, and it applies to the plan of the Service and to the plan of the runner Job (`--item`), because both call `plan_implement`.
- The check uses the constant `PLAN_NEEDS_FIX_LABEL` of `stage_verify.py`, the one that the stage job applies and the row `stage_ready` reads. The messages take the label as a value, so the code holds no second copy of the label text.
- The judge keeps the items that it leaves out for the label, and `ImplementPlan.needs_fix` returns them. The judge stays free of writes, because the module plans only.
- The row `implement` logs an item once for each draft. It records the draft in `implement.needs_fix`, as the row `stage_ready` records `stage.needs_fix` when it tells about the label once. A round clears the mark only for an item that its plan judged: with the limit 1 of the Service, the walk stops after the first item that it takes, and an item that it did not judge keeps its mark, so a later round does not log it again.
- When the label is gone, the item is free again at once: the judge reads the label in each round, and the mark gates only the log line.

## Rejected alternatives

- Leave out every unmerged plan, as #4078 and #4041 propose. That changes the Staged route of the job, which takes a plan on its staged branch by design. This change keeps that route and reads only the label that the review sets already.
- Read the check runs of the plan, as #3976 proposes. A plan with an open finding can pass every check, so the check runs do not show the finding.
- Comment on the issue when the job leaves the item out. The stage comment already lists the open findings, and the row `stage_ready` comments on the draft. A third comment adds noise for a person, so the Service logs the skip once and the plan report and `devops roadmap explain` give the reason.
- Log the skip in each round. The row runs every seven minutes, so a held item would add a log line in each round.

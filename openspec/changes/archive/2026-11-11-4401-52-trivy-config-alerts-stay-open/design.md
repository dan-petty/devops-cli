# Design

## Decisions

- **One group, one issue.** The key is the rule id and the path. One alert for each issue would make 52 issues at once, and one issue for a run would hold several fixes. The title is the key of the check for an open issue, so the check needs no state of its own.
- **The title is compared exactly.** An open issue with the same title means the group has an owner. The cost: intake can correct the type of a title (`fix` to `chore`), and the next run then files the group again. The filer limit of 5 bounds that cost. A hidden marker in the body would remove it, and the requirement of the issue asks for the title.
- **The worst severity first.** With a limit of 5, a CRITICAL alert never waits behind a LOW one.
- **A workflow, not a step of CI, and no `workflow_run`.** It needs `issues: write`, and a pull request run must not write issues. A `workflow_run` trigger would make zizmor report a HIGH finding (`dangerous-triggers`), one more alert with no judge, and the project allows no ignore of it. A daily schedule gives a new alert its issue in one day at most. The group `concurrency` stops two runs from filing the same issue.
- **Session and not `gh`.** The filer uses the GitHub session that `devops pr evidence` uses, so it paces and retries each request as the other commands do.
- **`.trivyignore.yaml` only for the IaC scan.** The image scans keep `.trivyignore` with `exp:`. The YAML form is the one that holds a path, a reason and an expiry, which a finding in one file of `k8s/` or `tf/` needs.
- **Judge and time.** The owner judges CRITICAL in 24 hours, because `SECURITY.md` forbids an agent to ignore CRITICAL. An agent judges the rest in 14 days, the longest total of an agent ignore.

## Rejected alternatives

- A rule in `SECURITY.md` only: it leaves the alert in the Security tab until a person looks.
- A job only: an issue with no judge and no time waits like the 52 alerts.
- A row on the status lane of the Service: it needs a new row, a setting and a token scope for work that CI already starts.
- A step in the CI workflow: a pull request run must not write issues.

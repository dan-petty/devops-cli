# Design

## Decisions

- **One window of 28 days for each SLO.** Prometheus keeps 30 days (`server.retention`), and a 30-day query at the edge of the retention loses its first samples. Sloth has a built-in 28-day window (`google-28d`) with the burn rates of Table 5-8 of the SRE workbook. #4709 already uses 28 days. The 30-day window of the service dashboards is a gap of #4709.
- **Measured windows of 7 and 30 days.** The Sloth rules do not exist yet, so the current state uses windows that a plain `increase()` can read. Each number gives its query and its date.
- **A rule that another document owns is a link.** AGENTS.md says that each rule lives in one document only. The spec owns a rule only when no document holds it on 2026-11-13. Table 1 routes the other rules, and the rules table holds no copy of them.
- **The owner document takes a missing rule.** The order of a new Secret goes to `k8s/README.md`, and the section rules of the dashboards go to `docs/DESIGN.md` as C15. The spec links to both.
- **The error budget policy is the policy of the SRE workbook.** The owner set the SLOs and the incident triggers. No document or issue sets the policy for a spent budget, so the spec takes the standard of the workbook.
- **The incident and supervise jobs are a contract, not a description.** No code holds them. The spec states what each job does and does not do, and #5477 holds the work. Only a person does the stop switch, so the supervise job uses only the controls of the Service.
- **An incident has a start, one record and an end.** It starts at the first crossing of a trigger, it has one open issue for each SLO or alert, and it ends after 1 hour at a burn rate of 1x or less. A silenced alert is not a trigger, so the jobs read the Alertmanager API, not `ALERTS`.
- **No routing row in AGENTS.md.** AGENTS.md has 4,222 characters against a cap of 4,500, and two sibling specs (#5443, #5444) come at the same time. The routing row of the cluster leads to `k8s/README.md` and `docs/CLUSTER.md`, which link the spec.

## Rejected alternatives

- **Write the spec as a section of `docs/CLUSTER.md`.** `docs/CLUSTER.md` has 119,858 characters and covers how devops-cli runs in the cluster. The SRE target, the incident steps and the gap table apply to every service of the cluster, not only to devops-cli.
- **Copy the alert tables into the spec.** `docs/CLUSTER.md` and `k8s/README.md` own the alert rules and their runbook rows, and tests pin them. A copy would make two documents for one rule.
- **A 30-day window, as the service dashboards use.** Rejected for the reason of the first decision.
- **Leave gaps as "new issue needed".** A merged spec with unfiled gaps breaks AGENTS.md rules 8 and 11. The change files 5 issues and comments on 6 open issues, so each gap has an issue.
- **Restate the rules of other documents in the rules table.** The copies of the Secret order and the dashboard rules drifted from their owners before the merge.

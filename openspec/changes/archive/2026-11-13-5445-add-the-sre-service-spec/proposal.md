# Proposal: #5445

## Why

The owner asked on 2026-11-13 for three project specs: SRE service implementation, Kubernetes performance tuning, and agentic workflow implementation and tuning (#5445). This change is the first spec.

The SRE rules of the project are in many documents, and some owner decisions are only in issues: the SLOs of 2026-11-11, Sloth for the SLO rules, the incident triggers, the Secret order and the error budget. No document gives the service catalog, the SLO of each service, the alert routing, the incident and postmortem steps, the backups, the capacity and the gaps with their issues. An agent that adds a service, an alert or a rollout cannot find the target or the open issue of a gap.

## What Changes

- Add `docs/SRE.md`, a normative spec in the form of `docs/DESIGN.md`: purpose and scope, principles, the service catalog, the target with numbers, the current state measured on 2026-11-13 with each query, the method, the rules SRE1 to SRE9, and the gap table.
- Each rule that another document owns is a link to that document, and the rules table holds no copy of it. The spec owns only the new rules: the service row and tier, the SLO in Sloth, the runbook row of an alert, the severity, the parked node silence, the incident and postmortem steps, the error budget policy and the restore test.
- `k8s/README.md` (Cluster Secrets) owns the order of a new Secret: a person pushes it from the branch before the merge of the manifest that reads it. The section said "after the merge". A required reference to a missing Secret stops its pod when Argo CD applies the manifest.
- `docs/DESIGN.md` gets chart rule C15 from the owner rules of 2026-11-12: one unit in each panel, the error ratio first in each section, then the golden signals. C12 (c) gives the page lines of a 28-day and a 30-day window.
- Add the spec to the docs site (`.nav.yml`) and to `docs/index.md`. Link it from `docs/DESIGN.md` ("Practice"), `docs/CLUSTER.md` (introduction) and `k8s/README.md` ("Alerting").
- The change alters no behavior that a consumer observes: it adds and links a document. So it has no spec delta and sets `skip_specs: true`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `docs/SRE.md` (new), `docs/index.md`, `.nav.yml`, `docs/DESIGN.md` (C12, C15), `docs/CLUSTER.md`, `k8s/README.md` (Alerting, Cluster Secrets).
- No code, test, manifest or setting changes. `AGENTS.md` does not change: the routing row "change a manifest, the cluster or OpenTofu" leads to `k8s/README.md` and `docs/CLUSTER.md`, which link the spec.
- A hand-written document needs no entry in `CONST_DOCS_INVENTORY` (`src/devops_cli/docs/inventory.py` computes the class).
- Each gap of the gap table has an open issue. The change files 5 issues as sub-issues of #5445 (#5471, #5473, #5475, #5477, #5480). It comments on #4560, #5143, #4742, #4714, #4709 and #3655 for the gaps that fit them.

## Feasibility

- Prometheus, through the Grafana datasource `prometheus`, at 2026-11-13T16:20Z: 72 alert rules in 21 groups (`sum by (rule_group) (prometheus_rule_group_rules)`), no recording rule with a colon in the name, and 453 notifications to Mattermost in 7 days with 0 failures. The other numbers of the spec name their query (Q1 to Q16).
- Read-only `kubectl` on the same date: 2 CloudNativePG clusters with 0 `ScheduledBackup` and 0 `Backup` objects, 16 claims on `local-path`, 34 Argo CD Applications, and `max_memory_limit: 16Gi` in the live ConfigMap `devops-cli-config`.
- The repository: the Service rollout (`k8s/devops/roadmap-service/deployment.yaml`, `Recreate`, `terminationGracePeriodSeconds: 660`), the Alertmanager route (`k8s/monitoring/prometheus-values.yaml`) and the service dashboards (`k8s/monitoring/dashboards/services.toml`).
- The SLOs and the incident triggers come from #4709 and #4714, which record the owner decisions of 2026-11-11.
- SLO 2 counts the runner Jobs only (`job_name=~"devops-cli-runner-.*"`): 91.1 % of 45 Jobs in 7 days and 96.0 % of 427 Jobs in 30 days. The fix-plan validation Jobs of the same namespace are not runner Jobs.
- Trigger 1 was not met: the row `stage` of devops-cli had at most 5 runs in any hour of 7 days (Q16), below the 20 events of the low-sample rule.
- 201 of the 224 `TargetDown` series-hours come from 3 scrape targets of the parked node (Q10 by `job`). #5143 holds the cause of the parked node.
- Read-only `kubectl` placement: the gateway database runs on the control-plane node, and the volume of the roadmap Service is on `local-path` on a worker node.
- No issue, document or code held the incident job or the supervise job on 2026-11-13 (issue search for `supervise` and `incident job`; `git grep -il supervise`). #5477 now holds them.
- Primary sources: the Google SRE book and workbook (Table 5-8 of "Alerting on SLOs", "Error Budget Policy", "Being On-Call", "Eliminating Toil", "Postmortem Culture", "Data Integrity") and the Sloth documentation of the built-in 28-day window (`google-28d`).

## Existing Tool Considered

The spec is a document, not code, and it names the open tools that do the work: Sloth for the SLO rules, Prometheus and Alertmanager for the alerts, Grafana for the dashboards, Argo CD for the changes and the Barman Cloud plugin of CloudNativePG for the backups. The cost was about 0.6 M tokens and 2 hours of elapsed time. The change deletes no internal code.

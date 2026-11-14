# SRE guideline

This guideline sets how a managed project runs its services by SRE practice. It covers the service catalog, the SLOs and error budgets, and the alerts. It also covers the incidents, the postmortems, the change safety, the backups, the capacity and the runbooks. For each topic, it gives the target, the method and the rules. It applies with no change to each managed project. The README of the environment tree of a project holds the decisions of its environment. These are the catalog data, the SLO objectives and the owner values that differ from a default of this guideline. They also include the accepted exceptions and the link to the gap tracker of the environment.

Other guidelines share the area. The [production readiness guideline](production-readiness.md) sets the rows that a service and a repository meet before a launch. The [Kubernetes guideline](kubernetes.md) owns the requests, the limits, the placement and the runtimes of the pods. The agentic jobs guideline owns the success, the limits and the tuning of an agentic job. [The guideline index](index.md) lists each guideline.

## Scope

The guideline applies to each service that a project runs in its Kubernetes cluster, and to each service that a job of the project calls. It applies to agents, to jobs and to a person who changes a service, an alert, a dashboard or a backup.

- **In scope.** The services of the catalog of the environment. Their SLIs, SLOs, error budgets, alerts, dashboards, incidents, postmortems, toil, rollouts, backups, capacity and runbooks. The production readiness of each service and each repository.
- **Not in scope.** The CI checks of a pull request ([AGENTS.md](../../AGENTS.md) rule 5 and [the SDLC](../SDLC.md)). The workstation and the devcontainer. The tuning of a pod (the Kubernetes guideline) and of an agentic job (the agentic jobs guideline).

Each rule lives in one document only. This guideline owns the rules of [Rules](#rules). For each other rule, it links to the document that owns it:

**Table 1.** The documents that own the rules that this guideline uses.

| Topic | Owner |
| :--- | :--- |
| The rows that a service and a repository meet, their levels, the readiness review and the steps of a new service | [The production readiness guideline](production-readiness.md) |
| The look of a dashboard, a chart, a report and a postmortem table | [The design spec](../DESIGN.md), rules C4, C7, C8, C12, C15 and T10, and the row "Grafana" of [Rules for each target](../DESIGN.md#rules-for-each-target) |
| No phone-home, private data and egress | [SECURITY.md](../../SECURITY.md) |
| A finding with no fix, and the response time of a vulnerability | [SECURITY.md](../../SECURITY.md#a-finding-with-no-fix) |
| Nested time limits | [ARCHITECTURE.md](../../ARCHITECTURE.md#6-sre-reliability-observability--quality-gates), section 6, "Nested Time Limits" |
| The alert rules, the receiver, the GitOps tool, the Secrets and the planned maintenance of one environment | The README of the environment tree |
| The alert rules, the go-live check and the stop switch of one product | The product document of the service |

## Principles

1. **The SLO drives the work.** Each service has an SLI that a user sees, and an SLO with an error budget. When the budget is spent, the work on that service is reliability work. This continues until the SLI is above the SLO again (SRE workbook, "Error Budget Policy").
2. **Alert on the symptom, page only for action now.** A page is for a burn of the error budget that needs a person within the hour. A cause, such as a full queue or a high request count, is a ticket (SRE workbook, "Alerting on SLOs").
3. **Git is the cluster.** Each change goes through a pull request and a GitOps tool. An object that git does not hold is drift.
4. **Automation before toil.** A step that a person does again and again, by hand, with no lasting value, is toil. Make a job or a command do it (SRE book, "Eliminating Toil").
5. **Postmortems have no blame.** A postmortem tells what the system let happen, not who did it. Each action item is an issue (SRE book, "Postmortem Culture").
6. **A backup is a restore that passed a test.** A backup with no restore test is not a backup (SRE book, "Data Integrity").
7. **Tools are open and replaceable.** Each tool connects through a standard interface: Prometheus rule files, Alertmanager receivers, OTLP, Kubernetes objects and git. A record that picks a tool says how to replace it.
8. **The system of record is the source.** A shared cache holds only copies, and a lost cache is built again from the system of record.
9. **Events start the automation.** An alert, a deploy or a schedule starts each automated step of the work. No service waits for the step, and a scheduled pass finds the work of a lost event. The agentic jobs guideline owns the rules of such a job.

## Service catalog

The tier sets the SLO, the alert severity and the backup of a service. Tier 1 serves the main user path of the project directly. Tier 2 is a dependency of tier 1. Tier 3 is the observability and the tools around them.

The catalog data of the environment gives each service its name, its GitOps applications, its tier, its data class ([Table 3](#backups-and-restores)) and its dependencies. The namespace, the workloads and the replicas of a service come from the rendered manifests. Do not copy them into a document. A Sloth spec names its service, and the service dashboard table names its workload, so the catalog data holds no SLO and no dashboard.

The owner role of each service is the project owner, who sets its SLO and approves its launch. Agents and jobs operate the services.

## Target

### SLOs and error budgets

The window is 28 days for each SLO. The window must stay inside the retention of the metrics store, and Sloth has a built-in 28-day window. The owner sets the objective of each SLO. The README of the environment tree holds each objective until the Sloth spec holds it.

An SLI is good events divided by valid events. An SLO with fewer than 20 events in the long window of an alert gives "low sample" and no alert.

### Burn-rate alerts

Sloth generates the recording rules and the alerts of each SLO from one spec. No person writes an SLO rule by hand. Each alert needs both of its windows above the burn rate. The burn rate is the error ratio divided by the budget ratio, `1 - objective`.

**Table 2.** The burn-rate alerts for a 28-day window: the built-in window catalog `google-28d` of Sloth. Sloth adapts Table 5-8 of the SRE workbook and adds the 1 d / 2 h ticket row.

| Severity | Long window | Short window | Budget spent | Burn rate (x) |
| :--- | :--- | :--- | ---: | ---: |
| Page | 1 h | 5 min | 2 % | 13.44 |
| Page | 6 h | 30 min | 5 % | 5.60 |
| Ticket | 1 d | 2 h | 10 % | 2.80 |
| Ticket | 3 d | 6 h | 10 % | 0.93 |

The burn rate of a window is the budget spent times 672 hours (28 days), divided by the long window in hours. [The design spec](../DESIGN.md#chart-rules) C12 (c) draws these page lines for a window of 28 or 30 days.

An SLO with fewer than 20 events in 1 hour gets no page alert, because of the low-sample rule. The 1 d and 3 d ticket windows show its burn.

### Notifications

- **Pages.** At most 2 incidents for each 12-hour on-call shift (SRE book, "Being On-Call"). The README of the environment tree sets the shifts of its owner, and so its page budget.
- **Tickets.** A ticket is an issue, or a comment on the open issue of its cause ([AGENTS.md](../../AGENTS.md) rule 11). A ticket does not notify a person at once.
- **Each alert has a runbook row** with a "Do this" step in the alert table of the document that owns its rule group.
- **Each notification is actionable.** An alert that fires with no action for 7 days is changed or removed. No action means that in 7 days no commit, no issue comment and no silence names the alert or its cause.

### Incidents and postmortems

An incident starts at the first crossing of a trigger of this list. The default triggers come from the SRE workbook:

1. A burn rate at or above the first page row of [Table 2](#burn-rate-alerts) for 1 hour or more, with at least 20 events. For a 28-day window, the rate is 13.44x.
2. 50 % or more of the budget of an SLO used in its window.
3. A critical alert, or a node that is not Ready, that fires for 30 minutes or more.
4. A revert commit on the default branch.

Keep the triggers as settings of the job that opens the incident, with these values as the defaults. When the owner sets another value, the README of the environment tree records it.

- **One record.** Each SLO or alert has at most one open incident issue. A trigger that stays true, such as trigger 2, opens no second incident.
- **Silences.** An alert that an active silence matches is not a trigger. Read the alert state from the Alertmanager API. The `ALERTS` series of Prometheus does not know the silences.
- **End.** An incident ends when 2 conditions are true for 1 hour. The 1 h burn rate of its SLO is 1x or less, and no critical alert of the incident fires. An incident with no SLO needs only the second condition.

Write a postmortem for each incident that used more than 20 % of the 28-day budget of one SLO (SRE workbook, "Error Budget Policy"). Also write one for each incident that lost data (SRE book, "Postmortem Culture").

### Change safety

- Each change of the cluster is a commit on the default branch that a GitOps tool applies. Drift is 0 objects. An object that git does not hold by design, such as a Secret, is an accepted exception. The README of the environment tree lists each one.
- A service that serves user requests keeps its route up during a rollout: 2 or more replicas, a rolling update with `maxUnavailable: 0`, and a PodDisruptionBudget. The product document of a service that cannot do this yet gives its rollout and the reason.
- Each deploy and each alert shows as a marker on the dashboards ([the design spec](../DESIGN.md#chart-rules) C8).

### Backups and restores

**Table 3.** The data classes and their target. The catalog data gives the class of each service.

| Class | Catalog value | Examples | Target |
| :--- | :--- | :--- | :--- |
| Truth outside the cluster | `external` | Issues, pull requests, labels and branches on the forge; git | No backup in the cluster. The forge holds it. |
| Derived | `derived` | Caches, vector indexes and other indexes that a job builds | No backup. A job builds it again from the truth. |
| Owned state | `owned` | A database, or a volume whose data no other source holds | A backup off its node at least once in 24 hours, so the RPO is 24 hours. A copy outside the cluster. A restore test once a month that writes its result as a metric. The owner sets the RTO of each store from the time of its first restore test. |
| Telemetry | `telemetry` | Metrics, logs, traces and profiles | No backup. The retention of the environment applies. |
| No data | `none` | A service that keeps no data between requests | No backup. |

### Capacity

- The request paths of tier 1 stay up when one worker node stops. The catalog gives the tier 1 services.
- State on a node-local volume stops with its node. The README of the environment tree lists each service that the owner accepts this for. The off-node backup of [Table 3](#backups-and-restores) limits the loss.
- A tier 2 service that holds only derived data can stop until a scheduled run builds it again on another node. While a shared cache is down, each read goes to the next tier or to the source.
- The requests of the pods that can move fit on the other nodes. Target T6 of the [Kubernetes guideline](kubernetes.md#targets) holds that check, and that guideline owns the requests and limits of each pod.

## Method

### States of an SLO

- **Met.** A burn rate of 1x or less, with 25 % or more of the budget left.
- **At risk.** A burn rate of 1x or less, with less than 25 % of the budget left ([the design spec](../DESIGN.md#chart-rules) C12 (a)).
- **Burning.** A burn rate above 1x in a window shorter than 28 days.
- **Breached.** A burn rate above 1x in a window of 28 days or more.

The service dashboards and the project review show the state of each SLO. No document copies a measured SLI, budget or state.

### SLIs and SLOs

1. Find the user of the service. Find the event that the user sees: a request, a job run or a Job.
2. Write the SLI as good events divided by valid events. Use a counter or a histogram that Prometheus already holds. Prefer the event that the user sends over a probe.
3. Write the SLO in the Sloth spec of the environment. Use the objective that the owner sets and a window of 28 days.
4. Generate the rules with Sloth, and test them with `promtool test rules`.
5. Add the service to the service dashboard table of the environment, and build the dashboards ([the design spec](../DESIGN.md#rules-for-each-target), row "Grafana").

A request that the service did not get is a bad event. An example is a webhook that the sender sent while no pod ran. When the server metric cannot count it, take the SLI from the client. For a webhook, the client is the sender, which records each delivery.

### Dashboards

The service dashboards come from one template in the layout of [the design spec](../DESIGN.md#chart-rules) C12 and C15. Do not edit a generated dashboard. Change its entry in the service dashboard table.

### Alerts and routing

- **Symptom alerts page.** The page alerts are the burn-rate alerts of Sloth and the critical alerts of the environment (rule SRE4).
- **Cause alerts are tickets.** A warning alert is a ticket. Its runbook row tells what to do and which issue to open or to comment on.
- **Routing.** Alertmanager sends each alert to its receiver. Send the pages to a channel that notifies a person. Send the tickets to issues through an Alertmanager webhook receiver.
- **Maintenance.** Silence a node before planned work. The README of the environment tree gives the steps. A parked node follows rule SRE5.

### Incident response

The SRE workbook ("Incident Response") gives the roles: the incident commander, the operations lead and the communications lead. The owner is the incident commander, and agents and jobs do the operations and the record.

1. **Detect.** A trigger of [Incidents and postmortems](#incidents-and-postmortems) fires.
2. **Declare.** Open the incident issue with `devops roadmap intake`, in the shape of the bug report form. Use the title `fix(<scope>): incident on SLO <n>, trigger <t>`. The words "incident on" in the title mark the record. In the body, write the trigger, the SLO and the start time in UTC.
3. **Mitigate first.** Stop the harm before you look for the cause. A person does the stop switch of the product. An agent opens a pull request that reverts the commit, or pauses the GitOps application.
4. **Record.** Add each step to the incident issue with its UTC time.
5. **Resolve.** Close the incident issue at the end of the incident ([Incidents and postmortems](#incidents-and-postmortems)).
6. **Review.** Write the postmortem when [Incidents and postmortems](#incidents-and-postmortems) asks for one.

A job does the detect, declare and record steps (principle 9):

- Send each Alertmanager notification to a webhook receiver. The receiver starts the job and does not wait for it.
- Run the same job on a schedule. The scheduled pass reads the triggers again, so a lost notification still opens the record.
- Use the SLO or the alert as the key of the record. A repeated notification then opens no second incident ([One record](#incidents-and-postmortems)).
- The job declares and records. It does not mitigate.

### Postmortems

- Write the postmortem in the incident issue, or in the postmortem section of the project review.
- Use the outline of the SRE book. Give the summary and the impact, with the SLI and the budget used. Give the UTC timeline, the root cause, the trigger, the detection and the resolution. End with the action items.
- Use the tables of [the design spec](../DESIGN.md#table-rules) T10 for the action items and the timeline.
- Follow rule SRE7. File each action item with `devops roadmap intake`, and link it from the postmortem.
- Close the postmortem only when each action item is closed, or when the owner accepts the risk in writing.
- Put each lesson into the document that owns its rule.

### Toil and automation

Toil is hand work on a service. It is repetitive, automatable and tactical, it has no lasting value, and it grows with the service (SRE book, "Eliminating Toil"). The SRE book keeps toil below 50 % of the time of each SRE.

- Count the hand steps of the owner each week. Count the items that wait for a person (`devops roadmap inbox`). Count the hand steps of the runbooks. Count the commands that a person runs again after a job.
- Show the hours of toil each week as [the design spec](../DESIGN.md#chart-rules) C12 (e) says.
- When a hand step occurs 3 times, file an issue. The issue makes a job or a command do the step.

### Error budget policy

Rule SRE8 applies from the time an SLO has spent its 28-day budget. It applies until the SLI is above its SLO again (SRE workbook, "Error Budget Policy").

### Deprecation and removal

A project with no compatibility guarantee removes the old path and adds no shim. Remove a part of a running service in this order:

1. Remove each user of the part first: the caller of a route, or the reference to a Secret key. For a setting, the live value changes before the image that stops reading it.
2. Then remove the part: the route, the row of the Secret table, or the setting of the template.
3. Remove the dashboards, the alert rules and the documents of the part in the same pull request.
4. Back up the data of its volume before its claim goes.

### Backups and restore tests

1. Put the data of the service in its class of [Table 3](#backups-and-restores).
2. For owned state, back up off the node with the tool of the store. Use the Barman Cloud plugin for a CloudNativePG cluster. Use the dump command of the application for the others.
3. Copy the backup to a target outside the cluster.
4. Run a restore test into a new namespace once a month. Compare a known record, and write the result and its age as a metric.
5. Alert when the last good backup or the last good restore test is older than its target.

### Capacity planning

- Read the use, the request and the limit of each tier 1 and tier 2 service. Its dashboard shows them ([the design spec](../DESIGN.md#chart-rules) C12 (f)).
- Check the loss of one worker node by the [Capacity](#capacity) target. A pod with a node-local volume cannot move to another node.
- Label a projection as a projection.
- Change a request or a limit by [the tuning loop](kubernetes.md#the-tuning-loop) of the Kubernetes guideline.

### Runbooks

The runbook of an alert is its row in the alert table of the document that owns its rule group. Each environment also has runbooks for the whole system. Examples are the stop switch of each product, the planned maintenance of a node and the recovery of the GitOps tool. The README of the environment tree links them.

### Cadence

**Table 4.** The routine work on the running services. Agents do each task that needs no person.

| Cadence | Task | Tool | Evidence |
| :--- | :--- | :--- | :--- |
| Each day | Read the firing alerts and the failed jobs. Renew or remove each ignore entry at its end date. | The `Alertmanager` datasource of Grafana; the ignore files of the scanners ([SECURITY.md](../../SECURITY.md#a-finding-with-no-fix)) | No firing alert without an issue; no ignore entry after its end date |
| Each week | Read the SLIs and the budgets, and apply rule SRE8. Count the toil. Read the dependency audit. | The service dashboards; [Toil and automation](#toil-and-automation); `devops ci audit` | A comment on the project review of the week |
| Each week | Read the costs: the model spend, the GitHub requests, the GPU power, the CI time and the cloud. | `devops ai cost report`; the spend and telemetry dashboards; `devops tf cost` | The same comment |
| Each month | Run the restore test of each store. Read the access: the App installations, the RBAC and the keyring entries. Read the health of the cluster resources. | [Backups and restore tests](#backups-and-restore-tests); `devops k8s rbac-audit`; `devops k8s audit` | The restore metric; a comment with the access review |
| Each quarter | Read the readiness report of each tier 1 and tier 2 service. | [The production readiness guideline](production-readiness.md) | The readiness report |

## Rules

Agents, jobs and persons obey these rules when they change a service, an alert, a dashboard or a backup. The other rules that apply to a service are in the documents of [Table 1](#scope). Do not copy them here.

| Rule | Rule text | Source |
| :--- | :--- | :--- |
| SRE1 | A new service gets an entry in the catalog data of the environment, with its tier, its data class and its dependencies. Its SLO goes in a Sloth spec. Add both in the pull request that adds the service. | This guideline |
| SRE2 | An SLO is an entry of the Sloth spec. Do not write an SLO recording rule or a burn-rate alert by hand. | Sloth |
| SRE3 | A new alert rule adds its row to the alert table of the document that owns its rule group. The row has a "Do this" step. Add the rule and the row in the same pull request. | This guideline |
| SRE4 | A critical alert needs a person within the hour. Each other alert is a warning, and a warning is a ticket. | SRE workbook, "Alerting on SLOs" |
| SRE5 | A parked node gets an Alertmanager silence with an end date, and an issue that holds the cause. Renew the silence only with a new comment on that issue. | This guideline |
| SRE6 | When a trigger of [Incidents and postmortems](#incidents-and-postmortems) fires, open one incident issue for each SLO or alert. Mitigate first. | SRE workbook, "Incident Response" |
| SRE7 | A postmortem names the conditions, not the persons or the agents. File each action item as an issue. | SRE book, "Postmortem Culture" |
| SRE8 | When an SLO has spent its 28-day budget, the jobs take only 3 kinds of item for its service. These are a fix of that SLO, a P0 item and a security fix. An item is for a service when its scope label or its changed paths name the service in the catalog. | SRE workbook, "Error Budget Policy" |
| SRE9 | A backup counts only after a restore test of it passed. | SRE book, "Data Integrity" |

## Sources

- Google SRE book: [Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/) (the four golden signals), [Eliminating Toil](https://sre.google/sre-book/eliminating-toil/), [Being On-Call](https://sre.google/sre-book/being-on-call/), [Managing Incidents](https://sre.google/sre-book/managing-incidents/), [Postmortem Culture](https://sre.google/sre-book/postmortem-culture/), [Data Integrity](https://sre.google/sre-book/data-integrity/).
- Google SRE workbook: [Implementing SLOs](https://sre.google/workbook/implementing-slos/), [Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/) (Table 5-8), [Error Budget Policy](https://sre.google/workbook/error-budget-policy/), [Incident Response](https://sre.google/workbook/incident-response/), [Postmortem Culture](https://sre.google/workbook/postmortem-culture/).
- Sloth: [Introduction](https://sloth.dev/introduction/) and [SLO period windows](https://sloth.dev/usage/slo-period-windows/) (the built-in 28-day and 30-day windows).
- Prometheus: [Alertmanager configuration](https://prometheus.io/docs/alerting/latest/configuration/) (routes, inhibitions and receivers).
- Kubernetes: [Deployment strategy](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#strategy) and [PodDisruptionBudget](https://kubernetes.io/docs/tasks/run-application/configure-pdb/).
- CloudNativePG: [Backup](https://cloudnative-pg.io/documentation/current/backup/).
- Production readiness: Google SRE book, [The Evolving SRE Engagement Model](https://sre.google/sre-book/evolving-sre-engagement-model/) and [Launch Coordination Checklist](https://sre.google/sre-book/launch-checklist/). The other standards are in [the production readiness guideline](production-readiness.md#sources).

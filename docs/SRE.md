# SRE spec

This spec sets how the project runs its services by SRE practice. It covers the service catalog, the SLOs and error budgets, and the alerts. It also covers the incidents, the postmortems, the change safety, the backups, the capacity and the runbooks. For each topic, it gives the target with numbers, the state on 2026-11-13, the method and the rules. A gap table maps each gap to its issue. Issue #5444 adds the Kubernetes performance tuning spec, which holds the requests, limits, placement and runtimes of the pods. Issue #5443 adds the agentic workflow spec, which holds the success, limits and tuning of the agentic jobs.

## Purpose and scope

The spec applies to each service that the project runs in its Kubernetes cluster, and to each service that a roadmap job calls. It applies to agents, to the roadmap jobs and to a person who changes a service, an alert, a dashboard or a backup.

- **In scope.** The services of [Table 2](#service-catalog), their SLIs, SLOs, error budgets, alerts, dashboards, incidents, postmortems, toil, rollouts, backups, capacity and runbooks.
- **Not in scope.** The CI checks of a pull request ([AGENTS.md](../AGENTS.md) rule 5 and [docs/SDLC.md](SDLC.md)). The workstation and the devcontainer. The tuning of a pod (#5444) and of an agentic job (#5443).

Each rule lives in one document only. This spec owns the rules of [Rules](#rules). For each other rule, it links to the document that owns it:

**Table 1.** The documents that own the rules that this spec uses.

| Topic | Owner |
| :--- | :--- |
| The look of a dashboard, a chart, a report and a postmortem table | [docs/DESIGN.md](DESIGN.md), rules C4, C7, C8, C12, C15 and T10, and the row "Grafana" of [Rules for each target](DESIGN.md#rules-for-each-target) |
| The alert rules of the environment, the receiver and the planned maintenance | [k8s/README.md](../k8s/README.md#alerting) |
| The alert rules of the roadmap Service, the go-live check, the live ConfigMap before the image, and the stop switch | [docs/CLUSTER.md](CLUSTER.md#alerts) |
| GitOps, drift and the Argo CD Applications | [k8s/README.md](../k8s/README.md#gitops) |
| The Secrets of the cluster, and the push of a new Secret before the merge | [k8s/README.md](../k8s/README.md#cluster-secrets) |
| The destination and the content of the spans | [docs/TELEMETRY.md](TELEMETRY.md#distributed-tracing--w3c-context-propagation), "OTLP Exporter", and [ARCHITECTURE.md](../ARCHITECTURE.md), "LLM inference spans", for devops-cli. [k8s/README.md](../k8s/README.md#gateway-spans) and the spec `openspec/specs/llm-telemetry-content/spec.md` for the gateway |
| No phone-home, private data and egress | [SECURITY.md](../SECURITY.md) |
| The metric instruments of devops-cli | [docs/TELEMETRY.md](TELEMETRY.md) |
| Nested time limits | [ARCHITECTURE.md](../ARCHITECTURE.md), section 6, "Nested Time Limits" |
| The success of each roadmap job, the job grades and the 80% rule | [docs/roadmap/job-success.md](roadmap/job-success.md) |
| The steps, gates and failure classes of a roadmap item | [docs/ROADMAP_WORKFLOW.md](ROADMAP_WORKFLOW.md) |
| The engine of the roadmap jobs and their shared state | [ADR 0008](adr/0008-argo-workflows-run-the-roadmap-jobs-after-a-measured-go.md), [ADR 0021](adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md), [ADR 0023](adr/0023-the-project-brain-is-a-derived-index-in-two-cache-tiers-and-two-scheduled-runs-keep-it.md) |
| A finding with no fix, and the response time of a vulnerability | [SECURITY.md](../SECURITY.md#a-finding-with-no-fix) |

## Principles

1. **The SLO drives the work.** Each service has an SLI that a user sees, and an SLO with an error budget. When the budget is spent, the work on that service is reliability work. This continues until the SLI is above the SLO again (SRE workbook, "Error Budget Policy").
2. **Alert on the symptom, page only for action now.** A page is for a burn of the error budget that needs a person within the hour. A cause, such as a full queue or a high request count, is a ticket (SRE workbook, "Alerting on SLOs").
3. **Git is the cluster.** Each change goes through a pull request and Argo CD. An object that git does not hold is drift ([k8s/README.md](../k8s/README.md#gitops)).
4. **Automation before toil.** A step that a person does again and again, by hand, with no lasting value, is toil. Make a job or a command do it (SRE book, "Eliminating Toil").
5. **Postmortems have no blame.** A postmortem tells what the system let happen, not who did it. Each action item is an issue (SRE book, "Postmortem Culture").
6. **A backup is a restore that passed a test.** A backup with no restore test is not a backup (SRE book, "Data Integrity").
7. **Tools are open and replaceable.** Each tool connects through a standard interface: Prometheus rule files, Alertmanager receivers, OTLP, Kubernetes objects and git. A record that picks a tool says how to replace it (#5427).
8. **GitHub is the truth.** Valkey holds shared coordination and cache state, and a lost cache is rebuilt from GitHub ([ADR 0021](adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md), [ADR 0023](adr/0023-the-project-brain-is-a-derived-index-in-two-cache-tiers-and-two-scheduled-runs-keep-it.md)).

## Service catalog

The tier sets the SLO, the alert severity and the backup of a service. Tier 1 serves the roadmap pipeline directly. Tier 2 is a dependency of tier 1. Tier 3 is the observability and the tools around them.

**Table 2.** The services, 2026-11-13. Source: `kubectl get deploy,statefulset,daemonset -A` and the Argo CD Applications.

| Service | Namespace | What it does | Tier | SLO |
| :--- | :--- | :--- | :--- | :--- |
| Roadmap Service (webhook router) | `devops` | Receives the GitHub webhooks, serves `/metrics` and the read API, and runs the rows of the roadmap jobs ([docs/CLUSTER.md](CLUSTER.md#roadmap-service)) | 1 | SLO 1, SLO 5 |
| Runner Jobs | `devops` | Run the implement job and the other one-item jobs in pods of their own | 1 | SLO 2 |
| LLM gateway (LiteLLM) | `llm` | Routes each model call to a model tier or a hosted provider | 1 | SLO 3, SLO 4 |
| Model tiers (Ollama) | `llm` | Serve the local models, one DaemonSet for each tier ([k8s/README.md](../k8s/README.md#gpu-placement-ollama-tiers)) | 2 | Through SLO 3 and SLO 4 |
| Gateway database (CloudNativePG) | `llm` | Holds the virtual keys and the spend logs of the gateway | 2 | Through SLO 3 |
| Valkey (3 instances) | `llm` | Holds shared coordination, cache and run index state | 2 | None yet |
| MCP server | `devops` | Serves the `devops` tools to the stage and implement jobs ([docs/CLUSTER.md](CLUSTER.md#mcp-server)) | 2 | None yet |
| Ingress (cloudflared and Traefik) | `cloudflared`, `kube-system` | Brings the GitHub webhooks and the read API to the roadmap Service | 2 | Through SLO 5 |
| Argo Workflows | `argo-workflows` | Runs the CronWorkflow `rag-ingest`. It will run the roadmap jobs after the steps of tracker #4517 ([ADR 0008](adr/0008-argo-workflows-run-the-roadmap-jobs-after-a-measured-go.md)) | 2 | None yet |
| Argo CD | `argocd` | Applies git to the cluster | 2 | None yet |
| Qdrant | `llm` | Holds the vector index of the project brain and the RAG ingestion | 2 | None yet |
| Crawl4AI and SearXNG | `devops` | Read web pages and search the web for the jobs | 3 | None yet |
| Prometheus, Alertmanager, Grafana, Loki, Tempo, Pyroscope, Alloy, OpenTelemetry Collector | `monitoring`, `logging`, `otel` | Collect, keep, show and alert on the metrics, logs, traces and profiles | 3 | None yet |
| Gitea and Mattermost | `gitea`, `mattermost` | The internal forge, and the channels of the alerts and the deploys | 3 | None yet |
| Object store (planned) | - | The content store and the backup target (#4742, #4750) | 2 | When it starts |
| Browser service (planned) | `devops` | A pinned Playwright server for agents and jobs (#5356) | 3 | When it starts |

Rule SRE1 adds each new service to this table.

## Target

### SLOs and error budgets

The owner set SLOs 1 to 4 on 2026-11-11. SLO 5 is the default of the service dashboards (`k8s/monitoring/dashboards/services.toml`) until the owner sets another target. The window is 28 days for each SLO. The window stays inside the 30 days that Prometheus keeps (`server.retention`), and Sloth has a built-in 28-day window.

**Table 3.** The SLOs. An SLI is good events divided by valid events.

| SLO | Service | SLI: good events / valid events | Objective | Error budget in 28 days |
| :--- | :--- | :--- | ---: | :--- |
| 1 | Roadmap Service | Row runs with `result="success"` / row runs with `result` `success` or `error`, for each row and repository (`devops_cli_service_jobs_total`) | 99.0 % | 1 % of the runs of each row and repository |
| 2 | Runner Jobs | Runner Jobs (`devops-cli-runner-*`) that end in under 3,600 s / runner Jobs that end | 90.0 % | 10 % of the Jobs, about 18 Jobs at the 7-day rate of [Table 6](#slis-and-error-budgets) |
| 3 | LLM gateway | Gateway requests with no failure / gateway requests (`litellm_proxy_*_requests_metric_total`) | 99.5 % | 0.5 % of the requests, about 1,370 requests at the rate of Table 6 |
| 4 | LLM gateway | Gateway requests that end in under 60 s / gateway requests (`litellm_request_total_latency_metric_bucket`) | 95.0 % | 5 % of the requests, about 13,700 requests at the rate of Table 6 |
| 5 | Roadmap Service | Ingress requests with no 5xx answer / ingress requests (`traefik_service_requests_total`) | 99.9 % | 0.1 % of the requests |

An SLO with fewer than 20 events in the long window of an alert gives "low sample" and no alert (#4709).

### Burn-rate alerts

Sloth generates the recording rules and the alerts of each SLO from one spec (#4709). No person writes an SLO rule by hand. Each alert needs both of its windows above the burn rate. The burn rate is the error ratio divided by the budget ratio, `1 - objective`.

**Table 4.** The burn-rate alerts for a 28-day window: the built-in window catalog `google-28d` of Sloth. Sloth adapts Table 5-8 of the SRE workbook and adds the 1 d / 2 h ticket row.

| Severity | Long window | Short window | Budget spent | Burn rate (x) |
| :--- | :--- | :--- | ---: | ---: |
| Page | 1 h | 5 min | 2 % | 13.44 |
| Page | 6 h | 30 min | 5 % | 5.60 |
| Ticket | 1 d | 2 h | 10 % | 2.80 |
| Ticket | 3 d | 6 h | 10 % | 0.93 |

The burn rate of a window is the budget spent times 672 hours (28 days), divided by the long window in hours. [docs/DESIGN.md](DESIGN.md#chart-rules) C12 (c) draws these page lines for a window of 28 or 30 days.

A row with fewer than 20 runs in 1 hour gets no page alert, because of the low-sample rule. The 1 d and 3 d ticket windows show its burn.

### Notifications

- **Pages.** At most 2 pages a day. The SRE book gives at most 2 incidents for each 12-hour on-call shift, and one owner holds one shift a day.
- **Tickets.** A ticket is an issue, or a comment on the open issue of its cause ([AGENTS.md](../AGENTS.md) rule 11). A ticket does not notify a person at once.
- **Each alert has a runbook row** with a "Do this" step in the table of the document that owns its rule group ([Table 1](#purpose-and-scope)).
- **Each notification is actionable.** An alert that fires with no action for 7 days is changed or removed. No action means that in 7 days no commit, no issue comment and no silence names the alert or its cause.

### Incidents and postmortems

An incident starts at the first crossing of a trigger of this list. The owner set the triggers on 2026-11-11 (#4714), from the SRE workbook:

1. A burn rate of 14.4x or more for 1 hour or more, with at least 20 events.
2. 50 % or more of the budget of an SLO used in its window.
3. A critical alert, or `NodeNotReady`, that fires for 30 minutes or more.
4. A revert commit on `main`.

Trigger 1 keeps the owner value 14.4x, the 1-hour page rate of a 30-day window, until the owner changes it. The 28-day page rate of [Table 4](#burn-rate-alerts) is 13.44x.

- **One record.** Each SLO or alert has at most one open incident issue. A trigger that stays true, such as trigger 2, opens no second incident.
- **Silences.** An alert that an active silence matches is not a trigger. Read the alert state from the Alertmanager API. The `ALERTS` series of Prometheus does not know the silences.
- **End.** An incident ends when 2 conditions are true for 1 hour. The 1 h burn rate of its SLO is 1x or less, and no critical alert of the incident fires. An incident with no SLO needs only the second condition.

Write a postmortem for each incident that used more than 20 % of the 28-day budget of one SLO (SRE workbook, "Error Budget Policy"). Also write one for each incident that lost data (SRE book, "Postmortem Culture").

### Change safety

- Each change of the cluster is a commit on `main` that Argo CD applies. Drift is 0 objects. Git does not hold 2 parts by design: the Secrets ([k8s/README.md](../k8s/README.md#cluster-secrets)) and ConfigMap `devops-cli-config` ([docs/CLUSTER.md](CLUSTER.md#go-live-check)).
- The roadmap Service keeps its webhook route up during a rollout: 2 replicas, `RollingUpdate` with `maxUnavailable: 0`, and a PodDisruptionBudget ([ADR 0021](adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md), section 1).
- Each deploy and each alert shows as a marker on the dashboards ([docs/DESIGN.md](DESIGN.md#chart-rules) C8, #5261).

### Backups and restores

**Table 5.** The data classes and their target.

| Class | Examples | Target |
| :--- | :--- | :--- |
| Truth outside the cluster | GitHub issues, pull requests, labels and branches | No backup in the cluster. GitHub holds it. |
| Derived | Valkey caches, the Qdrant index, the project brain | No backup. A job rebuilds it from the truth ([ADR 0023](adr/0023-the-project-brain-is-a-derived-index-in-two-cache-tiers-and-two-scheduled-runs-keep-it.md)). |
| Owned state | The gateway database, the Mattermost database and files, Gitea, and the volume `roadmap-service-home`, which the sweep keeps after [ADR 0021](adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md) | A backup off its node at least once in 24 hours. A copy outside the cluster. A restore test once a month that writes its result as a metric. |
| Telemetry | Prometheus, Loki, Tempo and Pyroscope data | No backup. The retention of [k8s/README.md](../k8s/README.md#log-and-metric-retention) applies. |

### Capacity

- The request paths of tier 1 stay up when one worker node stops. These are the webhook route of the roadmap Service, the LLM gateway and the start of new runner Jobs.
- State on a `local-path` volume stops with its node. [ADR 0021](adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md) accepts this for the sweep and its Valkey. The off-node backup of [Table 5](#backups-and-restores) limits the loss.
- A tier 2 service that holds only derived data can stop until a scheduled run builds it again on another node. While a shared cache is down, each read goes to the next tier or to the source ([ADR 0023](adr/0023-the-project-brain-is-a-derived-index-in-two-cache-tiers-and-two-scheduled-runs-keep-it.md), section 2).
- The requests of the pods that can move fit on the other nodes. Target T8 of the Kubernetes performance tuning spec (#5444) holds that check, and that spec owns the requests and limits of each pod.

## Current state

Measured on 2026-11-13 at 16:20 UTC with the Grafana datasource `prometheus` and with read-only `kubectl`. [Queries](#queries) holds each query. The 28-day Sloth rules do not exist yet, so this section uses windows of 7 and 30 days.

### SLIs and error budgets

**Table 6.** The SLIs. The burn rate over the window is the error ratio divided by the budget ratio. A value above 1 spends more than the budget of that window.

The states: **Met** is a burn rate of 1x or less, with 25 % or more of the budget left. **At risk** is a burn rate of 1x or less, with less than 25 % of the budget left ([docs/DESIGN.md](DESIGN.md#chart-rules) C12 (a)). **Burning** is a burn rate above 1x in a window shorter than 28 days. **Breached** is a burn rate above 1x in a window of 28 days or more.

| SLO | Window | Events (n) | SLI | Objective | Burn rate over the window (x) | State | Query |
| :--- | :--- | ---: | ---: | ---: | ---: | :--- | :--- |
| 1, all rows | 30 d | about 91,300 | 99.52 % | 99.0 % | 0.48 | Met | Q1 |
| 1, row `stage` of devops-cli | 7 d | 142 | 29.8 % | 99.0 % | 70.2 | Burning | Q2 |
| 1, row `refine` of devops-cli | 7 d | 151 | 90.7 % | 99.0 % | 9.3 | Burning | Q2 |
| 1, row `release_comments` of devops-cli | 7 d | 734 | 92.8 % | 99.0 % | 7.2 | Burning | Q2 |
| 2 | 7 d | 45 | 91.1 % | 90.0 % | 0.89 | Met | Q3 |
| 2 | 30 d | 427 | 96.0 % | 90.0 % | 0.40 | Met | Q3 |
| 3 | 7 d | 68,414 | 99.98 % | 99.5 % | 0.04 | Met | Q4 |
| 3 | 30 d | 129,417 | 99.38 % | 99.5 % | 1.24 | Breached | Q4 |
| 4 | 7 d | 68,414 | 97.2 % | 95.0 % | 0.56 | Met | Q5 |
| 4 | 30 d | 129,417 | 96.0 % | 95.0 % | 0.79 | At risk | Q5 |
| 5 | 7 d | 15,445 | 99.99 % | 99.9 % | 0.06 | Met | Q6 |

- 3 of the 91 pairs of a row and a repository with runs in 7 days are below 99 %. The 30-day ratio of all rows does not show them.
- The failures of SLO 3 in 30 days are mostly from 2026-10-24 to 2026-11-05. The highest day had 346 failed requests. Since 2026-11-07, each day has 8 failed requests or fewer.
- SLO 5 does not see the time with no pod. The Deployment of the roadmap Service had no available replica in 4.6 % of the minutes of 7 days, about 7.7 hours (Q7). 128 pods of the Service started in 7 days (Q15). Each release, each Secret push and each restart after a ConfigMap change starts a new pod with `Recreate`.
- The deployment-level success of the gateway is 97.88 % in 7 days (`litellm_deployment_*`). A fallback serves part of these failures, so the request-level SLI of SLO 3 is the user view.
- SLO 2 counts only the runner Jobs that end. kube-state-metrics shows a Job only while the Job object exists, and a failed Job has no completion time. 2 runner Jobs failed in 7 days. The fix-plan validation Jobs of namespace `devops` are not runner Jobs, so Q3 leaves them out.

### Alerts and notifications

- **Rules.** Prometheus evaluates 72 alert rules in 21 groups: 47 rules in 12 environment groups and 25 rules in 9 product groups (Q8). No rule is an SLO recording rule or a burn-rate alert (Q9). Grafana holds no managed alert rule.
- **Firing now.** 6 alerts: `NodeNotReady` (critical), 3 `TargetDown`, `RoadmapServiceItemStuck` and `RoadmapServiceWebhookDeliveriesFailed`. Alertmanager suppresses the 3 `TargetDown` alerts through the `NodeNotReady` inhibition (Q12). No silence is active.
- **Notifications.** Alertmanager sent 453 notifications to Mattermost in 7 days, about 65 a day, and 0 failed (Q11). `critical` and `warning` go to the same receiver ([k8s/README.md](../k8s/README.md#receiver)), so no notification is a page apart from a ticket.

**Table 7.** The alerts with the most firing time in 7 days, in series-hours: each firing series adds its hours (Q10).

| Alert | Severity | Firing (series-hours) |
| :--- | :--- | ---: |
| `RoadmapServiceItemStuck` | warning | 899.2 |
| `TargetDown` | warning | 224.2 |
| `NodeNotReady` | critical | 67.2 |
| `RoadmapServiceJobsFailing` | warning | 52.7 |
| `ClaudeSpendDailyHigh` | warning | 23.1 |
| `RoadmapServiceWebhookDeliveriesFailed` | warning | 19.6 |
| `HostedSpendDailyHigh` | warning | 18.6 |
| `ArgoCdApplicationUnhealthy` | warning | 18.6 |

- The `TargetDown` alerts of 3 scrape targets of the parked node give 201 of the 224 series-hours of `TargetDown` (Q10, by `job`).
- Each series of `RoadmapServiceItemStuck` is one item that waits for a person. `devops roadmap inbox` already lists these items.

### Incidents, restarts and OOM kills

- No incident record and no postmortem exist.
- Two incident triggers were met in the last 30 days, with no incident record:
  - Trigger 2: SLO 3 used 124 % of its budget.
  - Trigger 3: `NodeNotReady` fired for 67 hours.
- Trigger 1 was not met. The row `stage` of devops-cli burns at 70x over 7 days, but it had at most 5 runs in any hour (Q16). That is fewer than the 20 events of the low-sample rule.
- One node is parked (NotReady and cordoned) after crashes. #5143 holds the hardware tests and the cause. The node has no silence, so `NodeNotReady` repeats every 4 hours (`repeat_interval`).
- The containers of namespace `devops` restarted 89 times in 7 days. `mcp-server` restarted 85 times, all more than 3 days ago, and the Service container 3 times. 4 containers ended with `OOMKilled`: 3 of the Service and 1 of SearXNG (Q13). No alert watches a crash loop or an OOM kill of a pod other than the Service (#4993).

### Changes, backups and capacity

- **GitOps.** Argo CD holds 34 Applications: 32 are Synced and Healthy, and 2 are Synced and Progressing. 2 namespaces of a local test hold workloads that no Application manages.
- **Rollout of the roadmap Service.** One replica with `Recreate`. The stop of the Service waits 600 s for the drain and 30 s for the cut (`terminationGracePeriodSeconds: 660`, `CONST_SERVICE_STOP_GRACE_SECONDS`).
- **Runner memory.** The live ConfigMap sets `roadmap.implement.max_memory_limit` to `16Gi` since 2026-11-13, after an OOM kill at 8Gi. The deadline ceiling of a runner Job is 14,400 s, the limit of the admission policy `roadmap-service-jobs`.
- **Argo Workflows.** The controller runs. The measurement of 2026-11-11 gave a warm p95 of 11 s, and the owner recorded the go on #1535. The roadmap jobs do not run on Workflows yet. The only CronWorkflow is `rag-ingest`.
- **Backups.** 2 CloudNativePG clusters (`llm-gateway-db` and `mattermost-db`) run 1 instance each, with 0 `ScheduledBackup` and 0 `Backup` objects. The Barman Cloud plugin runs, but it has no object store target. Each of the 16 PersistentVolumeClaims is on `local-path`, so its data is on one node only. No restore test exists.
- **Capacity.** 4 nodes: 1 control-plane node, 2 Ready worker nodes and 1 parked node. The pods request 28.7 % of the allocatable CPU and 33.4 % of the allocatable memory of the Ready nodes. They use 18.4 % of that memory (Q14). The target is not met for the webhook route. The roadmap Service runs one pod, and its volume is on `local-path` on a worker node. So the pod cannot start on another node while that node is down. The gateway and its database run on the control-plane node, which the target does not cover.
- **Dashboards.** Grafana holds 18 dashboards. 2 come from the SRE template (`devops-roadmap-service` and `devops-sre-service`). No dashboard shows SLO 2, SLO 3 or SLO 4.
- **Toil.** No metric counts the hours of hand work.

### Queries

Each query ran as an instant query at 2026-11-13T16:20Z on the datasource `prometheus`, unless the item says otherwise.

- **Q1**, SLO 1 for all rows. For 7 days, replace `30d` with `7d`.

  ```promql
  sum(increase(devops_cli_service_jobs_total{job="roadmap-service", container="service", result="success"}[30d]))
    / sum(increase(devops_cli_service_jobs_total{job="roadmap-service", container="service", result=~"success|error"}[30d]))
  ```

- **Q2**, SLO 1 for each row and repository below the objective. The count of the pairs with runs is the same denominator with `> 0` and `count(...)`.

  ```promql
  sort(
    (sum by (row, repo) (increase(devops_cli_service_jobs_total{job="roadmap-service", container="service", result="success"}[7d]))
      / sum by (row, repo) (increase(devops_cli_service_jobs_total{job="roadmap-service", container="service", result=~"success|error"}[7d])))
    < 0.99)
  ```

- **Q3**, SLO 2, for the runner Jobs only. For n, remove `< 3600` and the division. For the failed runner Jobs, `count(max_over_time(kube_job_status_failed{namespace="devops", job_name=~"devops-cli-runner-.*"}[7d]) > 0)`.

  ```promql
  count(max_over_time(kube_job_status_completion_time{namespace="devops", job_name=~"devops-cli-runner-.*"}[7d]) - max_over_time(kube_job_status_start_time{namespace="devops", job_name=~"devops-cli-runner-.*"}[7d]) < 3600)
    / count(max_over_time(kube_job_status_completion_time{namespace="devops", job_name=~"devops-cli-runner-.*"}[7d]) - max_over_time(kube_job_status_start_time{namespace="devops", job_name=~"devops-cli-runner-.*"}[7d]))
  ```

- **Q4**, SLO 3. For n, `sum(increase(litellm_proxy_total_requests_metric_total[30d]))`. For each day, `sum(increase(litellm_proxy_failed_requests_metric_total[1d]))` as a range query with a step of 86,400 s.

  ```promql
  1 - sum(increase(litellm_proxy_failed_requests_metric_total[30d])) / sum(increase(litellm_proxy_total_requests_metric_total[30d]))
  ```

- **Q5**, SLO 4.

  ```promql
  sum(increase(litellm_request_total_latency_metric_bucket{le="60.0"}[30d])) / sum(increase(litellm_request_total_latency_metric_bucket{le="+Inf"}[30d]))
  ```

- **Q6**, SLO 5: the ingress requests by class of status code.

  ```promql
  sum by (code_class) (label_replace(increase(traefik_service_requests_total{service=~"devops-roadmap-service.*"}[7d]), "code_class", "${1}xx", "code", "(.).."))
  ```

- **Q7**, the share of the minutes of 7 days with no available replica of the roadmap Service.

  ```promql
  avg_over_time((sum(kube_deployment_status_replicas_available{namespace="devops", deployment="roadmap-service"}) < bool 1)[7d:1m])
  ```

- **Q8**, the alert rules of each group: `sum by (rule_group) (prometheus_rule_group_rules)`.
- **Q9**, the recording rules with a colon in the name, such as the `slo:` rules of Sloth: `count(count by (__name__) ({__name__=~".+:.+"}))`. The result is empty.
- **Q10**, the firing series-hours of each alert in 7 days: `sum by (alertname) (count_over_time(ALERTS{alertstate="firing"}[7d:5m])) / 12`. For `TargetDown` by target, select `alertname="TargetDown"` and sum by `job`.
- **Q11**, the notifications: `sum(increase(alertmanager_notifications_total{integration="mattermost"}[7d]))`, and the same with `alertmanager_notifications_failed_total`.
- **Q12**, the state of the alerts and the silences: `sum by (state) (alertmanager_alerts)` and `sum(alertmanager_silences{state="active"})`.
- **Q13**, the restarts and the OOM kills: `sum by (container) (increase(kube_pod_container_status_restarts_total{namespace="devops"}[7d]))` and `count by (container, reason) (max_over_time(kube_pod_container_status_last_terminated_reason{namespace="devops"}[7d]) == 1)`.
- **Q14**, the requests of the running pods as a share of the allocatable resources of the Ready nodes. For the use, divide `sum(container_memory_working_set_bytes{container!="", pod!=""})` by the same denominator for the memory.

  ```promql
  sum by (resource) (kube_pod_container_resource_requests{resource=~"cpu|memory"} * on (pod, namespace) group_left() (max by (pod, namespace) (kube_pod_status_phase{phase="Running"}) == 1))
    / sum by (resource) (kube_node_status_allocatable{resource=~"cpu|memory"} * on (node) group_left() (max by (node) (kube_node_status_condition{condition="Ready", status="true"}) == 1))
  ```

- **Q15**, the pods of the roadmap Service in 7 days: `count(count by (pod) (max_over_time(kube_pod_info{namespace="devops", pod=~"roadmap-service-.*"}[7d])))`.
- **Q16**, the most runs of the row `stage` of devops-cli in 1 hour, over 7 days with a step of 5 minutes.

  ```promql
  max_over_time((sum(increase(devops_cli_service_jobs_total{job="roadmap-service", container="service", row="stage", repo=~".*/devops-cli", result=~"success|error"}[1h])))[7d:5m])
  ```
- **kubectl**, read-only: `kubectl get clusters.postgresql.cnpg.io,scheduledbackups.postgresql.cnpg.io,backups.postgresql.cnpg.io -A`, `kubectl get pvc -A`, `kubectl get nodes`, `kubectl -n argocd get applications` and `kubectl get cronworkflows.argoproj.io -A`.

## Method

### SLIs and SLOs

1. Find the user of the service. Find the event that the user sees: a request, a row run or a Job.
2. Write the SLI as good events divided by valid events. Use a counter or a histogram that Prometheus already holds. Prefer the event that the user sends over a probe.
3. Write the SLO in the Sloth spec of #4709. Use the objective of [Table 3](#slos-and-error-budgets) and a window of 28 days.
4. Generate the rules with Sloth, and test them with `promtool test rules` (#4709).
5. Add the service to `k8s/monitoring/dashboards/services.toml`, and run `make dashboards` ([docs/DESIGN.md](DESIGN.md#rules-for-each-target), row "Grafana").

A request that the service did not get is a bad event. An example is a webhook that GitHub sent while no pod ran. When the server metric cannot count it, take the SLI from the client. For a webhook, the client is GitHub, which records each delivery (#4560).

### Dashboards

The service dashboards come from one template in the layout of [docs/DESIGN.md](DESIGN.md#chart-rules) C12 and C15. Do not edit a generated dashboard. Change its table in `services.toml`.

### Alerts and routing

- **Symptom alerts page.** The page alerts are the burn-rate alerts of Sloth and the critical alerts of [k8s/README.md](../k8s/README.md#alerting) (rule SRE4).
- **Cause alerts are tickets.** A warning alert is a ticket. Its runbook row tells what to do and which issue to open or to comment on.
- **Routing.** Alertmanager sends each alert to its receiver ([k8s/README.md](../k8s/README.md#receiver)). In the target, the pages go to the alert channel. The tickets go to issues through an Alertmanager webhook receiver (#5471).
- **Maintenance.** Silence a node before planned work ([k8s/README.md](../k8s/README.md#planned-maintenance)). A parked node follows rule SRE5.

### Incident response

The SRE workbook ("Incident Response") gives the roles: the incident commander, the operations lead and the communications lead. In this project, the owner is the incident commander, and agents and jobs do the operations and the record.

1. **Detect.** A trigger of [Incidents and postmortems](#incidents-and-postmortems) fires.
2. **Declare.** Open the incident issue with `uv run devops roadmap intake`, in the shape of `bug_report.yml`. Use the title `fix(<scope>): incident on SLO <n>, trigger <t>`. The words "incident on" in the title mark the record. In the body, write the trigger, the SLO and the start time in UTC.
3. **Mitigate first.** Stop the harm before you look for the cause. A person does the stop switch ([docs/CLUSTER.md](CLUSTER.md#stop-switch)). An agent opens a pull request that reverts the commit, or pauses the Application ([k8s/README.md](../k8s/README.md#pausing-an-application)).
4. **Record.** Add each step to the incident issue with its UTC time.
5. **Resolve.** Close the incident issue at the end of the incident ([Incidents and postmortems](#incidents-and-postmortems)).
6. **Review.** Write the postmortem when [Incidents and postmortems](#incidents-and-postmortems) asks for one.

#5477 adds two roadmap jobs that do parts of this work. Each job has one purpose, one due rule and one result line ([docs/roadmap/job-success.md](roadmap/job-success.md#the-result-line)):

- **The incident job** is due at the first crossing of a trigger. It reads the alert state from the Alertmanager API. It opens the incident issue with the trigger, the SLO and the burn rate. It adds the first timeline rows from the alerts, the releases and the commits of `k8s/`. It does not mitigate.
- **The supervise job** is due on a schedule. It reads the SLO state of each service. It also reads the state of each running job: a stall, a passed deadline or a spent budget. It acts only through the existing controls of the Service, such as the mode of a row. It applies rule SRE8, and it writes a ticket for each other finding.

### Postmortems

- Write the postmortem in the incident issue, or as the postmortem section of the project review (#4714).
- Use the outline of the SRE book. Give the summary and the impact, with the SLI and the budget used. Give the UTC timeline, the root cause, the trigger, the detection and the resolution. End with the action items.
- Use the tables of [docs/DESIGN.md](DESIGN.md#table-rules) T10 for the action items and the timeline.
- Follow rule SRE7. File each action item with `uv run devops roadmap intake`, and link it from the postmortem.

### Toil and automation

Toil is hand work on a service. It is repetitive, automatable and tactical, it has no lasting value, and it grows with the service (SRE book, "Eliminating Toil"). The SRE book keeps toil below 50 % of the time of each SRE.

- Count the hand steps of the owner each week. Count the items that wait for a person (`devops roadmap inbox`). Count the hand steps of the runbooks. Count the commands that a person runs again after a job.
- Show the hours of toil each week as [docs/DESIGN.md](DESIGN.md#chart-rules) C12 (e) says.
- When a hand step occurs 3 times, file an issue. The issue makes a job or a command do the step.

### Release and change safety

- **GitOps, settings and Secrets.** Follow the documents of [Table 1](#purpose-and-scope):
  - GitOps: [k8s/README.md](../k8s/README.md#gitops).
  - A change of a setting: the go-live check of [docs/CLUSTER.md](CLUSTER.md#go-live-check).
  - A new Secret: [k8s/README.md](../k8s/README.md#cluster-secrets).
- **Rollouts.** The roadmap Service uses `Recreate` with the drain of 600 s until the webhook router is stateless (#4575). Then it uses the rollout of [ADR 0021](adr/0021-the-roadmap-service-is-a-webhook-router-cluster-pods-run-the-roadmap-jobs-and-valkey-holds-their-shared-state.md), section 1.
- **Error budget policy.** Rule SRE8 applies from the time an SLO has spent its 28-day budget. It applies until the SLI is above its SLO again (SRE workbook, "Error Budget Policy").
- **Markers.** Each deploy writes a marker on the dashboards (#5261).

### Backups and restore tests

1. Put the data of the service in its class of [Table 5](#backups-and-restores).
2. For owned state, back up off the node with the tool of the service. Use the Barman Cloud plugin for a CloudNativePG cluster ([k8s/README.md](../k8s/README.md#cloudnativepg-backup-plugin)). Use the dump command of the application for the others.
3. Copy the backup to a target outside the cluster (#4770).
4. Run a restore test into a new namespace once a month. Compare a known record, and write the result and its age as a metric.
5. Alert when the last good backup or the last good restore test is older than its target.

### Capacity planning

- Read the use, the request and the limit of each tier 1 and tier 2 service. Its dashboard shows them ([docs/DESIGN.md](DESIGN.md#chart-rules) C12 (f)).
- Check the loss of one worker node by the [Capacity](#capacity) target. A pod with a `local-path` volume cannot move to another node.
- Label a projection as a projection.
- Change a request or a limit by the method of the Kubernetes performance tuning spec (#5444).

### Runbooks

The runbook of an alert is its row in the alert table of the document that owns its rule group. For the product rules, it is the "Do this" column of [docs/CLUSTER.md](CLUSTER.md#alerts). The environment rules of [k8s/README.md](../k8s/README.md#alerting) get their "Do this" column in #5471. These runbooks apply to the whole system:

- The stop switch ([docs/CLUSTER.md](CLUSTER.md#stop-switch)).
- The planned maintenance ([k8s/README.md](../k8s/README.md#planned-maintenance)).
- The recovery of Argo CD ([k8s/README.md](../k8s/README.md#recovery)).
- The section "Failure Recovery & Troubleshooting Matrix" of [docs/ROUTINE_TASKS.md](ROUTINE_TASKS.md).

## Rules

Agents, roadmap jobs and persons obey these rules when they change a service, an alert, a dashboard or a backup. The other rules that apply to a service are in the documents of [Table 1](#purpose-and-scope). Do not copy them here.

| Rule | Rule text | Source |
| :--- | :--- | :--- |
| SRE1 | A new service gets a row in [Table 2](#service-catalog), with a tier and an SLO. Add the row in the pull request that adds the service. | This spec |
| SRE2 | An SLO is an entry of the Sloth spec. Do not write an SLO recording rule or a burn-rate alert by hand. | #4709 |
| SRE3 | A new alert rule adds its row to the alert table of the document that owns its rule group. The row has a "Do this" step. Add the rule and the row in the same pull request. | This spec |
| SRE4 | A critical alert needs a person within the hour. Each other alert is a warning, and a warning is a ticket. | SRE workbook, "Alerting on SLOs" |
| SRE5 | A parked node gets an Alertmanager silence with an end date, and an issue that holds the cause. Renew the silence only with a new comment on that issue. | This spec. The silence before planned work is in [k8s/README.md](../k8s/README.md#planned-maintenance) |
| SRE6 | When a trigger of [Incidents and postmortems](#incidents-and-postmortems) fires, open one incident issue for each SLO or alert. Mitigate first. | #4714 |
| SRE7 | A postmortem names the conditions, not the persons or the agents. File each action item as an issue. | SRE book, "Postmortem Culture" |
| SRE8 | When an SLO has spent its 28-day budget, the jobs take only 3 kinds of item for its service. These are a fix of that SLO, a P0 item and a security fix. An item is for a service when its scope label or its changed paths name the service in [Table 2](#service-catalog). | SRE workbook, "Error Budget Policy" |
| SRE9 | A backup counts only after a restore test of it passed. | SRE book, "Data Integrity" |

## Gaps

Each gap has an open issue.

**Table 8.** The gaps between the target and the state of 2026-11-13.

| Gap | Issue |
| :--- | :--- |
| No SLO recording rule and no burn-rate alert exist (Q9). | #4709 |
| The project review shows no SLO, budget, incident or postmortem section. | #4714 |
| No dashboard or alert covers the roadmap pipeline as a whole. | #3655 |
| No alert watches a crash loop or an OOM kill outside the Service: `mcp-server` restarted 85 times with no alert. | #4993 |
| The dashboards show no deploy or alert marker. | #5261 |
| The roadmap Service runs one pod with `Recreate` on a `local-path` volume. It had no available replica in 4.6 % of the minutes of 7 days, and it stops with the node of its volume. | #4575 |
| A webhook that GitHub sent while no pod ran is lost. SLO 5 does not count it, because SLO 5 counts only the requests that reached Traefik. | #4560 (its gauge of failed deliveries gives the bad events of SLO 5) |
| SLO 3 used 124 % of its 30-day budget, with no incident record and no postmortem. | #5473 |
| The row `stage` of devops-cli is at 29.8 % over 7 days (SLO 1). | #5440 (the limits of the failing jobs), #5164 (the job grades), #5443 (the agentic workflow spec) |
| Pages and tickets go to one Mattermost receiver: 453 notifications in 7 days, against a target of 2 pages a day. | #5471 |
| The 47 rules of the 12 environment groups have no "Do this" step in [k8s/README.md](../k8s/README.md#alerting). | #5471 |
| `RoadmapServiceItemStuck` fired for 899 series-hours in 7 days with no action. | #3655 |
| The parked node fires `NodeNotReady` and 3 `TargetDown` alerts, with no silence. | #5143 |
| No incident job opens an incident record when a trigger fires. No supervise job reads the SLO state and the running jobs. | #5477 |
| No roadmap job applies the error budget policy (SRE8). | #5477 |
| No owned state has a backup off its node: 0 `ScheduledBackup` objects. | #3741 (gateway database), #4765 (Mattermost database), #4767 (other volumes), #2144 (Gitea) |
| No backup target outside the cluster and no object store exist. | #4770, #4750, tracker #4742 |
| No restore test exists, and no metric gives the age of the last good test. | #4742 (the restore drills, as a monthly run) |
| No metric counts toil. | #4714 (the toil facts of the project review) |
| The service dashboards use a 30-day window, and the Sloth spec of #4709 uses 28 days. | #4709 |
| SLO 2, SLO 3 and SLO 4 have no dashboard. | #5475 |
| The tier 2 services Valkey, the MCP server, Argo Workflows, Argo CD and Qdrant have no SLO. | #5475 |
| 2 namespaces of a local test hold workloads that no Argo CD Application manages, and no check finds them. | #5480 |

## Sources

- Google SRE book: [Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/) (the four golden signals), [Eliminating Toil](https://sre.google/sre-book/eliminating-toil/), [Being On-Call](https://sre.google/sre-book/being-on-call/), [Managing Incidents](https://sre.google/sre-book/managing-incidents/), [Postmortem Culture](https://sre.google/sre-book/postmortem-culture/), [Data Integrity](https://sre.google/sre-book/data-integrity/).
- Google SRE workbook: [Implementing SLOs](https://sre.google/workbook/implementing-slos/), [Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/) (Table 5-8), [Error Budget Policy](https://sre.google/workbook/error-budget-policy/), [Incident Response](https://sre.google/workbook/incident-response/), [Postmortem Culture](https://sre.google/workbook/postmortem-culture/).
- Sloth: [Introduction](https://sloth.dev/introduction/) and [SLO period windows](https://sloth.dev/usage/slo-period-windows/) (the built-in 28-day and 30-day windows).
- Prometheus: [Alertmanager configuration](https://prometheus.io/docs/alerting/latest/configuration/) (routes, inhibitions and receivers).
- Kubernetes: [Deployment strategy](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#strategy) and [PodDisruptionBudget](https://kubernetes.io/docs/tasks/run-application/configure-pdb/).
- CloudNativePG: [Backup](https://cloudnative-pg.io/documentation/current/backup/).

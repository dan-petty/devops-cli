# infra-apply Specification

## Purpose
How `devops infra apply` runs a saved plan of an infra repo on its hosts: the level that an agent needs, the guards of the plan, the commit, the host keys and the health of the cluster, one disruptive node at a time, the stops, the audit record and the dry run.

## Requirements

### Requirement: The level that an apply needs
An agent caller SHALL be refused with the error code `INFRA_ACCESS_REFUSED`, before any process starts, when the agent access level of the repo is below `safe`, or below `full` for a plan with a disruptive class or an unchecked task. A person SHALL apply at every level.

#### Scenario: An agent at plan
- **WHEN** an agent applies a plan on a repo at the level `plan`
- **THEN** the command exits 1, says that the apply needs `safe` and names `infra.repos[].agent_access`, and starts no process

#### Scenario: An agent at safe and a disruptive plan
- **WHEN** an agent applies a plan with `service-restart:k3s-agent` on a repo at the level `safe`
- **THEN** the command exits 1 and says that the apply needs `full`

#### Scenario: An agent at safe and a plan with no disruptive class
- **WHEN** an agent applies a plan with one changed task, no disruptive class and no unchecked task on a repo at the level `safe`
- **THEN** the apply ends `ok`

#### Scenario: A person at none
- **WHEN** a person applies a disruptive plan on a repo at the level `none`
- **THEN** the apply ends `ok`

### Requirement: The apply runs only the saved plan as it was
The command SHALL refuse a plan id that is not 64 lower-case hexadecimal characters, a plan that the repo does not have, a record whose facts do not give its id, a plan that failed, a plan older than `infra.plan_max_age_hours`, and a playbook, limit or tags other than the plan's, before any process starts.

#### Scenario: A changed record
- **WHEN** the record of the plan changed after the plan
- **THEN** the command exits 1, says that the record changed after the plan, and changes no node

#### Scenario: An old plan
- **WHEN** the plan ran 25 hours ago and `infra.plan_max_age_hours` is 24
- **THEN** the command exits 1 and names `infra.plan_max_age_hours`

#### Scenario: Another limit
- **WHEN** the plan has the limit `node-3.example.com` and the caller gives `node-4.example.com`
- **THEN** the command exits 1 and names both limits

#### Scenario: An id that is a path
- **WHEN** the caller gives `../../etc` as the plan id
- **THEN** the command says that it is not a plan id and reads no file

### Requirement: Origin holds the commit of the plan
After a fetch of `origin`, the command SHALL refuse a commit that the default branch, the head of the pull request of the plan's ref, or the branch of the plan's ref does not hold. An agent SHALL apply only a commit of the default branch, or at `full` the head of an open pull request whose head is the commit. The apply SHALL export that commit, never the working tree.

#### Scenario: A commit that origin does not hold
- **WHEN** no ref of origin holds the commit of the plan
- **THEN** the command exits 1, names the commit, and exports nothing

#### Scenario: An agent and another branch
- **WHEN** an agent applies a plan of `--ref fix/k3s` that the default branch does not hold
- **THEN** the command exits 1 and says that an agent applies only a commit of the default branch

#### Scenario: An agent and the head of a pull request
- **WHEN** an agent at `full` applies a plan of `--ref pull/19/head`
- **THEN** the apply goes on when pull request 19 is open at the commit, and exits 1 when it is closed

### Requirement: An agent apply needs host key checks on
The command SHALL refuse an agent apply when the config or the inventory of the commit turns host key checks off, and name each setting, before any node step.

#### Scenario: The inventory turns host key checks off
- **WHEN** a host of the inventory sets `ansible_ssh_common_args` to `-o StrictHostKeyChecking=no` and an agent applies
- **THEN** the command exits 1, names `StrictHostKeyChecking=no`, and drains no node

### Requirement: The cluster is healthy before the apply
The command SHALL refuse the apply when a node of the kube context that is not the node of a host out of service is not Ready or has memory, disk or PID pressure, or when `prometheus.url` is set and a `severity="critical"` alert fires or the query gets no answer. A query that gets no answer after the attempts of `SERVICE_READ_RETRY` SHALL be a problem of the gate whose text holds the line of `ServiceRequestError`. The gate SHALL keep its own wait loop.

#### Scenario: A node with memory pressure
- **WHEN** node-2 has `MemoryPressure` before the apply
- **THEN** the command exits 1, names node-2 and `MemoryPressure`, and drains no node

#### Scenario: A critical alert
- **WHEN** `prometheus.url` is set and the alert `KubeNodeNotReady` with `severity="critical"` fires
- **THEN** the health gate names the alert

#### Scenario: Prometheus answers only after the uncordon
- **WHEN** Prometheus does not answer the first two queries of the alert wait after a host, each after all of its attempts, then answers with no alert
- **THEN** the wait ends with no problem

#### Scenario: Prometheus stays down
- **WHEN** Prometheus answers 503 to each attempt of the query of the critical alerts
- **THEN** the health gate has one problem that names Prometheus, `503` and `4 attempts`

### Requirement: The hosts with no disruptive class run together
The hosts of a plan with no disruptive class SHALL run together in one run, with no drain, before the disruptive hosts.

#### Scenario: Hosts with no disruptive class
- **WHEN** a plan has node-4 with no disruptive class and node-3 with one
- **THEN** node-4 runs first with no drain, then node-3 runs alone

### Requirement: One disruptive host at a time
Each disruptive host SHALL run alone in plan order. A host whose classes are all `service-restart-nodrain:<unit>` SHALL be cordoned and SHALL NOT drain. Each other disruptive host SHALL take the drain check and the drain with no `--force`. Every disruptive host SHALL then take a fresh check that must equal its plan, the run, the Ready, GPU and node-health waits, the critical-alert wait when `prometheus.url` is set, and the uncordon only of a node that was schedulable before.

#### Scenario: Two disruptive hosts
- **WHEN** a person applies a plan of node-2 and node-1, both disruptive
- **THEN** the steps are the drain check, the drain, the check, the run and the uncordon of node-1, then the same of node-2

#### Scenario: A node that was cordoned before
- **WHEN** node-3 is cordoned before the apply
- **THEN** the apply ends `ok` and node-3 stays cordoned

#### Scenario: A no-drain restart of a host
- **WHEN** a person applies a plan whose host node-3 holds only the class service-restart-nodrain:k3s-agent
- **THEN** the steps are the cordon of node-3, the fresh check, the run, Ready, the health of the nodes and the uncordon of node-3, with no drain check and no drain

#### Scenario: The dry run of a no-drain host
- **WHEN** a person runs `devops infra apply --dry-run` on a plan whose host node-3 holds only the class service-restart-nodrain:k3s-agent
- **THEN** the listed steps hold the cordon of node-3 and no drain check and no drain

### Requirement: The drain waits for the grace period of each pod
The bound of the drain of a host SHALL be `infra.drain_timeout_seconds`, or the longest grace period of a pod that the drain evicts and 60 s, when that is longer.

#### Scenario: A pod with a long grace period
- **WHEN** node-3 has a pod of a ReplicaSet with a grace period of 660 s and the setting is 180 s
- **THEN** the drain of node-3 runs with `--timeout=720s`

### Requirement: The apply names the workloads that only the node can run
Before the drain check of a disruptive host, the command SHALL read the pods of its node, the PersistentVolumeClaims and the PersistentVolumes, and name each workload of a pod that the drain evicts and that mounts a claim whose volume only that node can mount (a required node affinity on `kubernetes.io/hostname` with the node alone). The report and the audit record of the host SHALL hold them. The apply SHALL not stop for them.

#### Scenario: A Deployment with a local volume
- **WHEN** a pod of the Deployment `apps/roadmap` on node-3 mounts a claim whose volume only node-3 can mount
- **THEN** the apply ends `ok`, prints that `apps/roadmap (Deployment)` is down during the apply of node-3, and the audit record of node-3 holds it

### Requirement: The waits go on through a gap of the API server
The waits for Ready and for health SHALL read again when a read fails, until `infra.node_ready_timeout_seconds` ends.

#### Scenario: The API server restarts
- **WHEN** kubectl fails 3 times after the run of the control-plane host
- **THEN** the apply ends `ok`

### Requirement: The first failure stops the apply
A drain check that fails SHALL stop the apply before the drain. A fresh check that differs from the plan SHALL stop it before the run of the host. A failed task, and a task that changed in the run and that the plan does not show as changed or unchecked, SHALL stop it. A wait or a health gate that does not pass SHALL stop it before the uncordon. A stop SHALL leave the node as the step left it, run no later host, and exit 1 with the host, the step and the reason.

#### Scenario: A blocked drain
- **WHEN** a PodDisruptionBudget blocks the drain check of node-3
- **THEN** the command exits 1, node-3 is not cordoned, and no drain runs

#### Scenario: A fresh check that differs
- **WHEN** the fresh check of node-3 shows one changed task less than the plan
- **THEN** the command exits 1 at the step `fresh check`, no run of node-3 starts, and node-3 stays cordoned

#### Scenario: An unplanned change
- **WHEN** the run of node-3 changes the task `Check if K3s agent binary exists`, which the plan does not show
- **THEN** node-3 stops at the step `run` with that task as unplanned and stays cordoned

#### Scenario: A health failure after a host
- **WHEN** node-4 is not Ready after the run of node-1
- **THEN** node-1 stops at the step `health` and stays cordoned, and node-2 does not run

### Requirement: Each apply writes an audit record
Each apply that passes the argument checks SHALL write one audit record `infra.apply` with its result (`ok`, `refused` or `stopped`), the caller and the level, with no secret and no path of a key, and add one to `devops_cli_infra_runs_total` with the repo, the command and the result.

#### Scenario: The record of an agent apply
- **WHEN** an agent at `full` applies a plan of node-3
- **THEN** the details of the last audit record are the id, the caller `agent`, the tool `claude_code`, the level, the repo, the commit, the ref, the plan id, the playbook, the limit, the tags, the result, the reason, the hosts, the alerts that the health gate left out and the duration; node-3 has its node, disruptive classes, outcome, step, reason, two runner idents and the workloads that were down; and the record holds no name or folder of the key of `devops ssh`

#### Scenario: The record of a refusal
- **WHEN** an agent applies on a repo at `plan`
- **THEN** the last audit record has the result `refused` and the reason

### Requirement: A person approves the apply
Without `--auto-approve`, the command SHALL ask a person before any process starts, and an answer of no SHALL exit 1 with nothing changed.

#### Scenario: A person says no
- **WHEN** a person answers `n`
- **THEN** the command exits 1, says that the apply was not approved, and starts no process

### Requirement: The dry run starts no process
`--dry-run` SHALL start no process and send no request, also for an agent at `none`, and list the commands of the apply in order, with the hosts of the plan record when it reads.

#### Scenario: A dry run of a plan of two hosts
- **WHEN** an agent at `none` gives `--dry-run` for a plan of node-4 and node-3
- **THEN** the command exits 0, starts no process, and lists the run of node-4, then the steps of node-3

### Requirement: The health gate leaves out the alerts of the nodes out of service
The gate before the apply and the alert wait after each host SHALL leave out a firing critical alert whose label `node`, else whose label `instance`, names the node of a host out of service. The report SHALL name each alert that they left out, once, and the audit record SHALL hold it. An alert with no such label, or for a node in service, SHALL still stop the apply.

#### Scenario: The alert of a node out of service
- **WHEN** `prometheus.url` is set, node-5 is the node of a host of the offline group, and `NodeNotReady` with `node="node-5"` fires through the apply of node-3
- **THEN** the apply ends `ok`, prints one line that it left out `NodeNotReady` of node-5 because node-5 is out of service, and the audit record holds that line

#### Scenario: The alert of a node in service
- **WHEN** `prometheus.url` is set and `NodeNotReady` with `node="node-2"` fires before the apply
- **THEN** the command exits 1, names the alert, and drains no node

#### Scenario: An alert with no node label
- **WHEN** `prometheus.url` is set, node-5 is out of service, and `ClusterMetricsMissing` with no label `node` or `instance` fires
- **THEN** the health gate names the alert as a problem

### Requirement: Each host of the together run is one term of the limit
The limit of the run of the hosts with no disruptive class SHALL name each host and the offline exclusion as separate comma-separated terms, so the run reaches every host of the plan and no host of the group of hosts out of service.

#### Scenario: A together run of two hosts
- **WHEN** a plan holds node-1 and node-4 with no disruptive class and the offline group is `offline`
- **THEN** the limit of their run is `node-1.example.com,node-4.example.com,!offline`

#### Scenario: The dry run shows each together host as its own term
- **WHEN** a dry run of the apply command reads a plan whose together run holds node-1 and node-4
- **THEN** the request plan shows `node-1.example.com,node-4.example.com,!<offline group>`

#### Scenario: The audit record names each cluster of the window
- **WHEN** an apply opens a maintenance window for `llm/llm-gateway-db`
- **THEN** the audit record of the host names `llm/llm-gateway-db`

### Requirement: Level gate for infra apply step job
The `infra-apply` step job SHALL refuse an infra repo whose agent access level is below `safe`.

#### Scenario: Refuse plan level
- **WHEN** a merged pull request of an infra repo at level `none` or `plan` starts the step job
- **THEN** the job writes no plan, makes no apply, and reports that the level is too low.

### Requirement: Plan before apply in step job
The `infra-apply` step job SHALL save an infra plan for the merge commit before it applies that plan.

#### Scenario: Plan the merge commit
- **WHEN** the step job starts for a merged pull request at level `safe` or `full`
- **THEN** the job saves the plan for the merge commit and calls `apply_saved_plan` only with that plan.

### Requirement: Apply only an ok plan
The `infra-apply` step job SHALL apply only an infra plan that ended `ok`.

#### Scenario: Failed plan
- **WHEN** the plan for the merge commit ended `failed`
- **THEN** the job makes no apply and reports the failed plan.

### Requirement: Stop before own node and control-plane node
The `infra-apply` step job SHALL stop before a disruptive host that is its pod node or the control-plane node and report a workstation run.

#### Scenario: Own node in the plan
- **WHEN** the plan has a disruptive host that is the node of the step job pod or the control-plane node
- **THEN** the job stops before that host, uncordons no node, and posts a message that names the host and the workstation run.

### Requirement: One comment per merge
The `infra-apply` step job SHALL post exactly one comment on the merged pull request for each merge.

#### Scenario: Comment with result and audit record
- **WHEN** the step job finishes
- **THEN** it posts one comment with the result and the audit record, with a hidden marker keyed by the merge commit.

#### Scenario: Deduplicate comments
- **WHEN** the step job runs again for the same merge commit
- **THEN** it edits the existing comment instead of posting a new one.

### Requirement: One issue per failure
The `infra-apply` step job SHALL open or update one issue in the infra repo when an apply fails or stops.

#### Scenario: Issue on failure
- **WHEN** the step job fails or stops
- **THEN** it opens or updates an issue in the infra repo with the failure details.

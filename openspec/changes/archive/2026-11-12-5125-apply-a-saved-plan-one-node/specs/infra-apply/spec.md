## Purpose

How `devops infra apply` runs a saved plan of an infra repo on its hosts: the level that an agent needs, the guards of the plan, the commit, the host keys and the health of the cluster, one disruptive node at a time, the stops, the audit record and the dry run.

## ADDED Requirements

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
The command SHALL refuse the apply when a node of the kube context that is not the node of a host out of service is not Ready or has memory, disk or PID pressure, or when `prometheus.url` is set and a `severity="critical"` alert fires or the query gets no answer.

#### Scenario: A node with memory pressure
- **WHEN** node-2 has `MemoryPressure` before the apply
- **THEN** the command exits 1, names node-2 and `MemoryPressure`, and drains no node

#### Scenario: A critical alert
- **WHEN** `prometheus.url` is set and the alert `KubeNodeNotReady` with `severity="critical"` fires
- **THEN** the health gate names the alert

#### Scenario: Prometheus answers only after the uncordon
- **WHEN** Prometheus does not answer the first two queries of the alert wait after a host, then answers with no alert
- **THEN** the wait ends with no problem

### Requirement: The hosts with no disruptive class run together
The hosts of a plan with no disruptive class SHALL run together in one run, with no drain, before the disruptive hosts.

#### Scenario: Hosts with no disruptive class
- **WHEN** a plan has node-4 with no disruptive class and node-3 with one
- **THEN** node-4 runs first with no drain, then node-3 runs alone

### Requirement: One disruptive host at a time
Each disruptive host SHALL run alone in plan order: the drain check (`kubectl drain --dry-run=server`), the drain with no `--force`, a fresh check-mode run that must equal its plan, the run, a wait for Ready and the GPUs of before, a wait for the health of every node, the uncordon only when the node was schedulable before the drain, and a wait for the critical alerts to clear when `prometheus.url` is set.

#### Scenario: Two disruptive hosts
- **WHEN** a person applies a plan of node-2 and node-1, both disruptive
- **THEN** the steps are the drain check, the drain, the check, the run and the uncordon of node-1, then the same of node-2

#### Scenario: A node that was cordoned before
- **WHEN** node-3 is cordoned before the apply
- **THEN** the apply ends `ok` and node-3 stays cordoned

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
- **THEN** the details of the last audit record are the id, the caller `agent`, the tool `claude_code`, the level, the repo, the commit, the ref, the plan id, the playbook, the limit, the tags, the result, the reason, the hosts and the duration; node-3 has its node, disruptive classes, outcome, step, reason, two runner idents and the workloads that were down; and the record holds no name or folder of the key of `devops ssh`

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

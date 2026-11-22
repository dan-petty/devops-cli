## Purpose

How `devops infra node drain|uncordon|restart|reboot <repo> <host>...` changes the nodes of the hosts of an infra repo one host at a time: the level that an agent needs, the hosts, the steps of each operation, the stops, the audit record and the dry run.

## ADDED Requirements

### Requirement: The level of each node operation
An agent caller SHALL be refused with the error code `INFRA_ACCESS_REFUSED`, before any process starts, when the agent access level of the repo is below `safe` for `uncordon`, or below `full` for `drain`, `restart` and `reboot`. A person SHALL run each operation at every level.

#### Scenario: The safe level allows only the uncordon
- **WHEN** an agent runs each of the four operations on one host of a repo at the level `safe`
- **THEN** `uncordon` exits 0 and the fake kubectl records `kubectl uncordon`; `drain`, `restart` and `reboot` exit 1, name `infra.repos[].agent_access`, and start no process

#### Scenario: A person at none
- **WHEN** a person runs `node drain` on one host of a repo at the level `none`
- **THEN** the run ends `ok`

### Requirement: Force only from a person
The drain check and the drain SHALL pass `--force` to `kubectl drain` only when the caller gives `--force`. An agent caller that gives `--force` SHALL be refused with the error code `INFRA_NODE_REFUSED` before any process starts.

#### Scenario: Force needs the flag
- **WHEN** a person runs `node drain` on one host with no `--force`, and again with `--force`
- **THEN** the first recorded `kubectl drain` calls have no `--force`, and the second recorded `kubectl drain` calls have `--force`

#### Scenario: An agent gives force
- **WHEN** an agent runs `node drain` with `--force` on a repo at the level `full`
- **THEN** the command exits 1, says that only a person gives `--force`, and starts no process

### Requirement: The hosts of a node operation
The command SHALL read the inventory of the repo at the head of its default branch at `origin`, and SHALL refuse with the error code `INFRA_NODE_REFUSED`, before any `kubectl` or `ansible-runner` process starts, a given host that is not a host of the inventory or that is in the group of hosts out of service.

#### Scenario: A host that the inventory does not have
- **WHEN** a person runs `node drain` on `node-9.example.com`, which the inventory does not have
- **THEN** the command exits 1, names `node-9.example.com`, and the fake kubectl records no call

### Requirement: The drain order
The `node drain` command SHALL run the health gate, read the node, check the drain with `kubectl drain --dry-run=server`, and then run `kubectl drain <node> --ignore-daemonsets --delete-emptydir-data --timeout=<bound>s`, in that order.

#### Scenario: Drain checks before it cordons
- **WHEN** a person runs `node drain` on one host with the default settings and a fake kubectl that records each call
- **THEN** the recorded calls show the health gate (`kubectl get nodes`), the read of the node, `kubectl drain --dry-run=server`, then `kubectl drain <node> --ignore-daemonsets --delete-emptydir-data --timeout=180s`, in that order, and the node is cordoned

### Requirement: The drain bound
The drain SHALL stop at `infra.drain_timeout_seconds`, or at the longest grace period of a pod that the drain evicts and 60 s, when that is longer.

#### Scenario: A long grace period extends the bound
- **WHEN** a person runs `node drain` with `infra.drain_timeout_seconds` at 180 and a fake kubectl that gives one pod on the node with a grace period of 900 s
- **THEN** the recorded `kubectl drain` call that is not the drain check has `--timeout=960s`

### Requirement: The uncordon order
The `node uncordon` command SHALL read the node, run `kubectl uncordon`, and then wait for the health gate.

#### Scenario: Uncordon comes before the health gate
- **WHEN** a person runs `node uncordon` on one cordoned host with a fake kubectl
- **THEN** the recorded calls show the read of the node, `kubectl uncordon`, and then the health gate, and the node is schedulable

### Requirement: The restart steps
The `node restart` command SHALL run the drain steps, restart the unit of `devops_infra_node_service` with an ansible-runner ad-hoc task `ansible.builtin.systemd_service name=<unit> state=restarted` with become, wait for Ready with the allocatable GPU count of before, run `kubectl uncordon` only when the node was schedulable before, and then wait for the health gate.

#### Scenario: Restart follows the drain
- **WHEN** a person runs `node restart` on one schedulable host with a fake kubectl and a fake ansible-runner
- **THEN** the recorded steps are the health gate, the read, the drain check, the drain, the restart of the unit `k3s-agent`, the wait for Ready, `kubectl uncordon` and the health gate, in that order, and the ad-hoc task has `--become`

#### Scenario: A template unit is rendered before the drain
- **WHEN** a person runs `node restart` on a host whose `devops_infra_node_service` is a template
- **THEN** an ad-hoc `ansible.builtin.debug` task renders it before the first `kubectl` call, and the restart task gets the rendered unit

### Requirement: Restart keeps the cordon
The `node restart` and `node reboot` commands MUST NOT uncordon a node that was cordoned before the run.

#### Scenario: A cordoned node stays cordoned
- **WHEN** a person runs `node restart` on a host whose node is already cordoned
- **THEN** the recorded calls hold no `kubectl uncordon`, the node stays cordoned, and the command exits 0

### Requirement: A restart needs a unit
The `node restart` command MUST refuse with the error code `INFRA_NODE_REFUSED` a host that sets no `devops_infra_node_service`, or whose value is not a systemd unit name, before any `kubectl` call and before the restart of any host.

#### Scenario: No unit, no restart
- **WHEN** a person runs `node restart` on a host with no `devops_infra_node_service` in its host variables
- **THEN** the command exits 1, names `devops_infra_node_service`, and the fake kubectl and the fake ansible-runner record no call

### Requirement: The reboot steps
The `node reboot` command SHALL run the drain steps, reboot the host with an ansible-runner ad-hoc task `ansible.builtin.reboot` with become, wait for Ready with a boot ID other than the one before and with the allocatable GPU count of before, run `kubectl uncordon` only when the node was schedulable before, wait for the health gate, and show the kernel of the node before and after.

#### Scenario: Reboot shows both kernels
- **WHEN** a person runs `node reboot` on one schedulable host with a fake kubectl and a fake ansible-runner whose reboot gives the node a new kernel and a new boot ID
- **THEN** the output holds the kernel of the node before and after the reboot, and the health gate follows `kubectl uncordon`

#### Scenario: The status of before the reboot does not end the wait
- **WHEN** the node gives the boot ID of before the reboot on the first reads after the reboot task
- **THEN** the wait goes on until the node gives a new boot ID

### Requirement: One host at a time
The command SHALL run one host at a time in the given order, and MUST stop at the first failure: the hosts after it do not run.

#### Scenario: The second host waits
- **WHEN** a person runs `node drain` on two hosts and the drain check of the first host fails
- **THEN** the command exits 1, the result is `refused`, and the fake kubectl records no call for the node of the second host

### Requirement: A failure keeps the cordon
The command MUST leave the node cordoned when a step after the drain fails.

#### Scenario: A failed wait keeps the cordon
- **WHEN** a person runs `node restart` on two hosts and the node of the first host is not Ready after the restart
- **THEN** the recorded calls hold no `kubectl uncordon`, the node stays cordoned, the second host does not run, and the command exits 1 with the result `stopped` and the step `ready`

### Requirement: The audit record and the counter of a node run
Each run that passes the argument checks SHALL write one audit record `infra.node.<operation>` with the operation, the caller and its tool, the level, the repo, the given hosts and the result `ok`, `refused` or `stopped`, and each host with its node, unit, outcome, step, reason and the cordon state and kernel before and after. It SHALL add one to `devops_cli_infra_runs_total` with the command `node <operation>` and the result.

#### Scenario: One record and one count for each run
- **WHEN** a person runs a `node drain` that ends `ok`, then a `node drain` on two hosts whose second drain check fails
- **THEN** the audit log holds two `infra.node.drain` records with the results `ok` and `stopped`, and the counter adds one for each with the command `node drain`

### Requirement: A dry run of a node operation does nothing
The command MUST start no process and send no request when the caller gives `--dry-run`, at every level. It SHALL list the commands of the run in order.

#### Scenario: Dry run makes no request
- **WHEN** an agent runs each of the four operations with `--dry-run` on a repo at the level `none`
- **THEN** each exits 0, no process starts, and the output lists the drain, the unit restart or the reboot, and the uncordon that the operation runs

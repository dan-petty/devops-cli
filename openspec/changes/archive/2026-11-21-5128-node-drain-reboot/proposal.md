# Proposal: #5128 drain, uncordon, restart and reboot one node at a time

## Why

Closes #5128. dan-petty/homelab has one Makefile target for each host and operation (`drain-<host>`, `uncordon-<host>`, `restart-<host>` for five hosts) and `rolling-restart`. Each target needs a person and has no health gate. The `restart-*` targets drain inside an Ansible play, and the play of `rolling-restart` skips a node that is already cordoned, so a drain from outside cannot combine with it. The owner decided on 2026-11-12 that agents may drain, restart k3s and reboot one node at a time, with dan-petty/homelab at the level `full` (tracker #5120, design sections 5 and 7). `devops infra apply` (#5125) already has the drain, the waits, the health gate and the audit record for a playbook; there is no command that does one node operation with the same guards.

## What Changes

- A new command group, `devops infra node`, with four commands: `drain`, `uncordon`, `restart` and `reboot`. Each takes `<repo> <host>...` and `--path`, `--format` and `--dry-run`; `drain`, `restart` and `reboot` also take `--force`. The commands run one host at a time in the given order and stop at the first failure.
- **Access level.** An agent needs the level `safe` for `uncordon` and `full` for `drain`, `restart` and `reboot`. A person may run each command at every level. An agent that gives `--force` is refused: only a person passes `--force` to the drain.
- **Hosts.** The command reads the inventory of the repo at the head of its default branch at `origin`, as `devops infra status` does. Each given host must be a host in service of the inventory. The node of a host is `devops_infra_node_name`, else the first DNS label of the host.
- **Steps.**
  - `drain`: the health gate, the read of the node (its cordon state, kernel and GPUs), the workloads that only the node can run, the drain check (`kubectl drain --dry-run=server`), and `kubectl drain --ignore-daemonsets --delete-emptydir-data --timeout=<bound>`. The bound is `infra.drain_timeout_seconds`, or the longest grace period of a pod that the drain evicts and 60 s, when that is longer. `--force` goes to the drain check and the drain only when a person gives it.
  - `uncordon`: the read of the node, `kubectl uncordon`, then the health gate.
  - `restart`: the steps of `drain`, then an ansible-runner ad-hoc task `ansible.builtin.systemd_service name=<unit> state=restarted` with become, the wait for Ready with the GPUs of before, `kubectl uncordon` only when the node was schedulable before, and the health gate. The unit is the host variable `devops_infra_node_service`. A host that sets no unit is refused before any process of the cluster or the hosts starts. A value that is a template is rendered with an ad-hoc `ansible.builtin.debug` task, which opens no SSH connection.
  - `reboot`: the steps of `restart` with an ad-hoc `ansible.builtin.reboot` task in place of the unit restart. The wait for Ready also waits for a new boot ID of the node, and the report shows the kernel of the node before and after.
- **Guards.** An agent restart or reboot is refused when the config or the inventory of the repo turns host key checks off, as an agent apply is.
- **Stops.** The first step that fails stops the run. The node stays as the step left it, cordoned after a drain, and the hosts after it do not run. A guard or a step that fails before the first change gives the result `refused`; a step that fails after the first change gives `stopped`. The command exits 1 in both cases.
- **Audit and telemetry.** Each run writes one audit record `infra.node.<operation>` with the caller and its tool, the level, the repo, the commit of the inventory, the hosts, `--force`, the result and each host with its node, unit, outcome, step, reason, the cordon state and the kernel before and after. It adds one to `devops_cli_infra_runs_total` with the command `node <operation>`.
- `--dry-run` starts no process and sends no request: it lists the commands of the run in order.
- `infra/nodes.py`: `drain_args` and the drain of `Cluster` take `force`; `Cluster.wait_ready` can wait for a new boot ID. A new module `infra/ad_hoc.py` builds and runs an ansible-runner ad-hoc task and reads its job events; the SSH check of `devops infra status --ping` uses it.
- A new error code, `INFRA_NODE_REFUSED`. New defaults for the bound of the unit restart (300 s), the bound of the reboot (600 s) and the margin of their process bounds (120 s).
- CONTEXT.md gets the term "Node command". SECURITY.md names the uncordon at the level `safe` and the node commands in the guards of `## Infra Repos`.

## Capabilities

- `infra-node` (new): the level of each operation, the hosts, the steps of each operation, the drain bound and `--force`, the unit of a restart, the kernel of a reboot, the stops, the audit record and the counter, and the dry run.

## Impact

- Four new commands, one new error code and three new defaults. No setting changes: the commands read `infra.drain_timeout_seconds`, `infra.node_ready_timeout_seconds` and `prometheus.url`.
- `devops_cli_infra_runs_total` gets the command values `node drain`, `node uncordon`, `node restart` and `node reboot`. No dashboard or alert rule reads the label `command`.
- The commands change hosts. A drained node takes no new pods until a person or `uncordon` makes it schedulable again; `restart` and `reboot` uncordon only a node that was schedulable before.
- dan-petty/homelab#22 removes the Makefile targets that these commands replace.
- The change fits one pull request.

## Feasibility

- **The node service variable.** dan-petty/homelab#21 is closed. On 2026-11-21 the group variables of `k3s_cluster` in dan-petty/homelab set `devops_infra_node_service: "{{ 'k3s' if node_role == 'server' else 'k3s-agent' }}"`, so the raw value of `ansible-inventory --list` is a template and only Ansible renders it. The `ansible.cfg` of the repo sets `become = True`.
- **The drain and the uncordon.** `Cluster.drain_check`, `Cluster.drain`, `Cluster.drain_bound`, `Cluster.down_during_apply`, `Cluster.uncordon` and the waits of `src/devops_cli/infra/nodes.py` ran live in the apply of #5125 on the homelab cluster (k3s v1.37.2+k3s1). The Kubernetes reference of `kubectl drain` gives `--ignore-daemonsets`, `--delete-emptydir-data`, `--timeout` and `--force` (https://kubernetes.io/docs/reference/kubectl/generated/kubectl_drain/).
- **The boot ID.** The Kubernetes API reference of `NodeSystemInfo` gives `bootID` and `kernelVersion` (from `uname -r`), which the kubelet reports (https://kubernetes.io/docs/reference/kubernetes-api/cluster-resources/node-v1/). A reboot gives a new boot ID, so the wait does not pass on the status that the node posted before the reboot.
- **The ad-hoc tasks.** ansible-core 2.22.0 is the pinned tool (`src/devops_cli/tools_lock/ansible-core.in`). `ansible.builtin.systemd_service` and `ansible.builtin.reboot` are modules of ansible-core; `reboot` waits until the host answers again with a new boot time, within `reboot_timeout` (default 600 s). The `ansible` ad-hoc command takes `--become` and `--task-timeout`. `devops infra status --ping` runs an ad-hoc task through `ansible-runner run <folder> --hosts <pattern> -m <module> -a <args>` and reads its job events; the new tasks use the same command line.
- **No live run here.** The live runs of the acceptance criteria (a reboot and a restart of a node of dan-petty/homelab at the level `full`) change real hosts, so this change proves the steps with a fake kubectl and a fake ansible-runner. The live runs come after the merge.

## Existing Tool Considered

kubectl does the drain, the drain check and the uncordon; ansible-runner with the ansible-core modules `systemd_service` and `reboot` does the restart and the reboot; `record_audit_event` writes the record; the guards and the waits of #5125 are shared. kured reboots nodes with a lock and alert gates, but it acts only when a reboot sentinel exists, and it has no restart and no command for one node, so a later item can add it for unattended kernel reboots. The tools lack the health gate, the order, the recorded cordon state, the first-failure stop and the audit record; this change adds them around the tools. The written cost to build the orchestration is about 2.5M tokens, 0.3M tokens a quarter to keep it, and 3 hours. The change deletes `ping_argv`, `ping_env` and the job event reader of `infra/status.py`, which `infra/ad_hoc.py` replaces, and moves `read_job_events` from `infra/plan.py` to `infra/ad_hoc.py`.

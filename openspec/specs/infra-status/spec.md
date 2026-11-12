# infra-status Specification

## Purpose
How `devops infra status` shows each host of an infra repo with the state of its Kubernetes node, and how `--ping` checks SSH to each host in service and whether it waits for a reboot, at the agent access level `plan` or above for an agent.

## Requirements

### Requirement: One row for each host with its node
`devops infra status <repo>` SHALL give one row for each host of the inventory at the head of the default branch at `origin`, sorted, then one row for each Kubernetes node that no host names, sorted. Without `--ping` the command MUST NOT start an Ansible run or an SSH connection.

#### Scenario: Cordoned, not Ready, offline and unknown nodes
- **WHEN** node-2 is cordoned, node-3 is not Ready, the hosts in `offline` have no node, and the cluster has node-9, which no host names
- **THEN** node-2 shows cordoned, node-3 shows Ready `False`, each host in `offline` shows no node, node-9 has a row with no host after the hosts, and no `ansible-runner` process starts

### Requirement: The facts of a row
A row SHALL hold the groups of the host, whether it is in service (not in the group of hosts out of service), and its node from the Kubernetes API of `infra.repos[].kube_context`: Ready, cordoned, kernel, kubelet, memory capacity, allocatable memory and allocatable GPUs.

#### Scenario: A node with 16 GiB
- **WHEN** node-2 has the memory capacity and the allocatable memory `16310540Ki` and one `nvidia.com/gpu`
- **THEN** its row holds `16701992960` bytes for both and one GPU, and the table shows `15.6 / 15.6`

### Requirement: The node of a host
The node of a host SHALL be its host variable `devops_infra_node_name`, else the first DNS label of the inventory name. A templated value SHALL give the default, because only Ansible renders a template.

#### Scenario: The host variable names the node
- **WHEN** node-4.example.com sets `devops_infra_node_name: gpu-4`
- **THEN** its row shows the node `gpu-4`

### Requirement: The SSH check
With `--ping`, the command SHALL run one `ansible-runner` ad-hoc `ansible.builtin.stat` of `/run/reboot-required` on the hosts in service, with the inventory of the profile, a connection bound of 10 s, no `become`, the key of `devops ssh` when it exists and host key checks on. Each host in service SHALL show `reachable` with whether a reboot waits, `unreachable` or `failed` with the reason, or `no answer`.

#### Scenario: An agent on a repo at plan
- **WHEN** an agent runs the command with `--ping` on a repo at `plan`, and node-1 has `/run/reboot-required`
- **THEN** node-1 shows `reachable` and a reboot that waits, and each host in `offline` has no check

### Requirement: The SSH check needs the level plan
An agent caller of `--ping` SHALL be refused with the error code `INFRA_ACCESS_REFUSED` when the agent access level of the repo is below `plan`, before any request.

#### Scenario: An agent on a repo at none
- **WHEN** an agent runs `devops infra status <repo> --ping` on a repo at `none`
- **THEN** the command exits 1, names the level `plan` and the setting `infra.repos[].agent_access`, and makes no Kubernetes call and starts no process

### Requirement: Output formats and the dry run
The command SHALL print a table under a title and the commit that it read with `--format table`, the default, and the report model with `--format json` or `yaml`. With `--dry-run`, it SHALL make no request and start no process, also for an agent on a repo at `none`, and SHALL list the Kubernetes call, the git commands of the read, the inventory listing and, with `--ping`, the `ansible-runner` run.

#### Scenario: A dry run of the SSH check
- **WHEN** an agent runs the command with `--ping --dry-run` on a repo at `none`
- **THEN** the command exits 0, makes no Kubernetes call, starts no process and lists the requests in order

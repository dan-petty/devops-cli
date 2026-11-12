# Proposal: #5123 show the hosts of an infra repo with node state

## Why

Closes #5123. To see the hosts of dan-petty/homelab, a person ran `scripts/cluster-status.sh` and `scripts/health-check.sh`, or read `kubectl get nodes` and the inventory side by side. On 2026-11-10 the node `hawk` hung and came back with 16 GiB; nothing showed the inventory and the node state together. Tracker #5120 names `devops infra status` as the second command, and `plan`, `apply` and `node` need the same join of hosts and nodes.

## What Changes

- A new command, `devops infra status <repo>`. It reads the inventory at the head of the default branch at `origin` (the shared reader of #5162) and the nodes of the kube context of `infra.repos[].kube_context`. It gives one row for each host: groups, in service or in the group of hosts out of service, node, Ready, cordoned, kernel, kubelet, memory capacity, allocatable memory and allocatable GPUs. A node that no host names gets a row after the hosts. The node of a host is `devops_infra_node_name`, else the first DNS label.
- `--ping` adds one `ansible-runner` ad-hoc run of `ansible.builtin.stat` on `/run/reboot-required` on the hosts in service: SSH reachability and a reboot that waits, from the job events of the run. The run uses the repo's `ansible.cfg` and inventory, the key of `devops ssh`, no `become`, a connection bound of 10 s and host key checks on.
- `infra/access.py: require_agent_level` refuses an agent below the level that an action needs. `--ping` needs `plan`.
- `--format table|json|yaml` and `--dry-run`, which makes no request.
- The node builder of the Kubernetes fake takes the kernel, the kubelet and the resources of a node.

## Capabilities

- `infra-status` (new): the rows of the hosts and nodes of an infra repo, the SSH check and its access level, the output formats and the dry run.

## Impact

- One new command. No setting changes. The default `DEFAULT_INFRA_PING_TIMEOUT_SECONDS` (300 s) bounds the SSH check.
- Without `--ping`, the command reads the Kubernetes API and fetches `origin`; it starts no SSH connection.
- `--ping` connects to each host in service and reads one file. It changes nothing on a host.

## Feasibility

- The live run on 2026-11-12 on dan-petty/homelab read `origin/main` and the kube context `homelab-k3s`: 4 hosts in service with their nodes, 2 hosts in `offline` with no node, `hawk` cordoned with 15.5 GiB, and allocatable memory equal to capacity on every node (homelab #19 is merged and not applied). `condor` runs kernel 7.2.8 and the other nodes 7.2.15. `--ping` reached the 4 hosts in service, and none waits for a reboot. The output is in a comment of the pull request.
- ansible-runner 2.4.3 in the pinned tool environment: `ansible-runner run <dir> --hosts all -m ansible.builtin.stat -a path=/run/reboot-required "--cmdline=-i <inventory> -T 5"` wrote `runner_on_ok` with `res.stat.exists` for a reachable host and `runner_on_unreachable` with `res.msg` for a host at 192.0.2.1, in `<artifact dir>/<ident>/job_events/<counter>-<uuid>.json`. The run starts `ansible` from PATH, with the private data folder as its working folder, so the command puts the tool environment first on PATH and gives the export as that folder. `--cmdline` takes its value after `=`: `--cmdline -i ...` is read as the option `-i` of ansible-runner. ansible-runner sets `ANSIBLE_HOST_KEY_CHECKING=False` unless the environment sets it, so the command sets it to `True`.
- `kubernetes.utils.quantity.parse_quantity` of the pinned `kubernetes` 36.0.3 reads `16310540Ki` and `15000Mi` as bytes.

## Existing Tool Considered

The Kubernetes API through the existing `KubernetesService`, `parse_quantity` of the `kubernetes` client, ansible-runner for the SSH check and its job events, and the shared reader of the default branch give every fact. The command joins them: about 1.5M tokens to build, 0.2M tokens a quarter to keep and fix, and 2 hours, as #5123 estimated. A second `ping` run was not added: the `stat` run shows that a host answers, and it reads the reboot file in the same connection.

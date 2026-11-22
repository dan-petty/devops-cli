# `devops infra`

Manage an infra repo: a git repository with an Ansible inventory, its playbooks and roles. The settings name each infra repo and its agent access level (infra.repos).

## Commands

## `devops infra onboard`

**Check an Ansible infra repo for what devops infra needs, and print one row for each check with its state and the next step. The check fetches origin and reads the head of the default branch, not the working tree of the checkout, with local tool output. It installs the pinned collections of the repo into a temporary folder to list their roles. With --confirm, write the entry of the repo in infra.repos, at agent access none unless a person gives --agent-access.**

```bash
devops infra onboard [OPTIONS] <repo>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo>` | `string` | Yes | The infra repo: owner/name, or the folder of a checkout, which its remote origin names. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--path` | `path` | - | The folder of the checkout. Default: the path of the entry, else <repos.base_dir>/\<owner\>/\<name\>. |
| `--kube-context` | `string` | - | The kubectl context of the cluster whose nodes are hosts of the repo. It goes in the entry. |
| `--ssh-key-prefix` | `string` | - | The devops ssh prefix of the key that Ansible connects with. Default: the prefix of the entry, else ansible. |
| `--agent-access` | `choice (none|plan|safe|full)` | - | What an agent may do on the hosts of the repo: none, plan, safe or full. Only a person gives a level above none. Default: the level of the entry, else none. |
| `--confirm` | `boolean` | - | Write the entry of the repo in infra.repos of the active config file. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops infra status`

**Show each inventory host of an infra repo with the state of its Kubernetes node: Ready, cordoned, kernel, kubelet, memory capacity and allocatable memory, and GPUs. The hosts come from the head of the default branch at origin, and the nodes from the kube context of the entry. With --ping, also check SSH to each host in service and whether it waits for a reboot.**

```bash
devops infra status [OPTIONS] <repo>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo>` | `string` | Yes | The infra repo: owner/name, or the folder of a checkout, which its remote origin names. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--path` | `path` | - | The folder of the checkout. Default: the path of the entry, else <repos.base_dir>/\<owner\>/\<name\>. |
| `--ping` | `boolean` | - | Connect to each host in service with SSH and read /run/reboot-required. An agent needs the agent access level plan or above. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops infra plan`

**Run a playbook of an infra repo in check mode with diffs on its hosts in service, and show for each host the changed tasks, the disruptive changes (reboot, service-restart:\<unit\>, service-restart-nodrain:\<unit\>, drain), the changes with the diff hidden and the tasks that check mode skipped. A changed restart of a unit that the host lists in devops_infra_restart_nodrain_units gets service-restart-nodrain:\<unit\>: the apply cordons the node and skips the drain check and the drain. The run exports a commit that origin holds, by default the head of the default branch, never the working tree. It changes no host. The plan record and the runner artifacts stay in <data dir>/infra/\<owner\>/\<name\>/plans/\<id\>/. An agent needs the agent access level plan or above.**

```bash
devops infra plan [OPTIONS] <repo> <playbook>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo>` | `string` | Yes | The infra repo: owner/name, or the folder of a checkout, which its remote origin names. |
| `<playbook>` | `string` | Yes | The playbook, as a path from the repo root, such as ansible/playbooks/site.yaml. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--limit` | `string` | - | The hosts or groups to plan, as an Ansible host pattern. Default: all hosts. The hosts of the group of hosts out of service are never in the plan. |
| `--tags` | `string` | - | Run only the tasks with these Ansible tags, separated by commas. |
| `--ref` | `string` | - | The ref at origin to plan: a branch of origin, or pull/\<number\>/head for the head of a pull request. Default: the default branch. |
| `--path` | `path` | - | The folder of the checkout. Default: the path of the entry, else <repos.base_dir>/\<owner\>/\<name\>. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops infra apply`

**Apply a saved plan of devops infra plan to the hosts of an infra repo. The apply needs the plan id and the playbook, limit and tags of the plan, a plan not older than infra.plan_max_age_hours, a commit that origin holds and a healthy cluster. The hosts with no disruptive change run together. Each disruptive host runs alone in plan order: drain check, drain, a fresh check that must equal the plan, the run, Ready with the GPUs of before, the health of the nodes, uncordon only when the node was schedulable before, and no critical alert. A host whose disruptive classes are all service-restart-nodrain:\<unit\> is cordoned instead, because the restart of such a unit keeps its containers: the cordon, the fresh check, the run, Ready, the health of the nodes, the uncordon only when the node was schedulable before, and no critical alert, with no drain check and no drain. The health checks leave out the nodes of the hosts out of service and each critical alert whose node label names one of them, and the report names each alert that they left out. The drain waits for the longest grace period of a pod of the node, and the apply names each workload that is down while the node is cordoned, because only that node can mount its volume. A change that the plan does not show, or the first failure, stops the apply. Each apply writes an audit record. An agent needs the agent access level safe for a plan with no disruptive change and no unchecked task, else full; an agent applies only a commit of the default branch, or at full the head of an open pull request, and only with host key checks on. An agent runs the command as one plain command: the project allow rule Bash(uv run devops *) lets it start, and the owner keeps that rule. A compound shell line (an assignment, ;, &&, |) goes to the auto-mode classifier. The agent access level of the repo is the real control.**

```bash
devops infra apply [OPTIONS] <repo> <playbook>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo>` | `string` | Yes | The infra repo: owner/name, or the folder of a checkout, which its remote origin names. |
| `<playbook>` | `string` | Yes | The playbook of the plan, as a path from the repo root. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--plan` | `string` | - | The id of the saved plan, as devops infra plan printed it. |
| `--limit` | `string` | - | The --limit of the plan. The apply refuses a plan with another limit. |
| `--tags` | `string` | - | The --tags of the plan. The apply refuses a plan with other tags. |
| `--path` | `path` | - | The folder of the checkout. Default: the path of the entry, else <repos.base_dir>/\<owner\>/\<name\>. |
| `--auto-approve` | `boolean` | - | Apply with no question. An agent gives it. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops infra node`

**Drain, uncordon, restart or reboot the Kubernetes nodes of the hosts of an infra repo, one host at a time in the given order. The hosts come from the inventory at the head of the default branch at origin. The first failure stops the run and leaves the node as the step left it, cordoned after a drain. Each run writes an audit record.**

```bash
devops infra node COMMAND [ARGS]...
```

### `devops infra node drain`

**Drain the node of each host: the health gate, the drain check (kubectl drain --dry-run=server), then kubectl drain --ignore-daemonsets --delete-emptydir-data. The drain waits for infra.drain_timeout_seconds, or for the longest grace period of a pod of the node and 60 s when that is longer, and names each workload that is down while the node is cordoned. An agent needs the agent access level full.**

```bash
devops infra node drain [OPTIONS] <repo> <hosts>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo>` | `string` | Yes | The infra repo: owner/name, or the folder of a checkout, which its remote origin names. |
| `<hosts>` | `string` | Yes | The inventory hosts, in the order to run them. Each must be a host in service. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--force` | `boolean` | - | Pass --force to the drain: it also deletes each pod that no controller owns. Only a person gives it. |
| `--path` | `path` | - | The folder of the checkout. Default: the path of the entry, else <repos.base_dir>/\<owner\>/\<name\>. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops infra node uncordon`

**Uncordon the node of each host, then wait for the health gate. An agent needs the agent access level safe.**

```bash
devops infra node uncordon [OPTIONS] <repo> <hosts>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo>` | `string` | Yes | The infra repo: owner/name, or the folder of a checkout, which its remote origin names. |
| `<hosts>` | `string` | Yes | The inventory hosts, in the order to run them. Each must be a host in service. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--path` | `path` | - | The folder of the checkout. Default: the path of the entry, else <repos.base_dir>/\<owner\>/\<name\>. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops infra node restart`

**Drain the node of each host, restart the unit of devops_infra_node_service with an Ansible ad-hoc task, wait for Ready with the GPUs of before, uncordon only a node that was schedulable before, and wait for the health gate. A host that sets no devops_infra_node_service is refused before any change. An agent needs the agent access level full and host key checks on.**

```bash
devops infra node restart [OPTIONS] <repo> <hosts>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo>` | `string` | Yes | The infra repo: owner/name, or the folder of a checkout, which its remote origin names. |
| `<hosts>` | `string` | Yes | The inventory hosts, in the order to run them. Each must be a host in service. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--force` | `boolean` | - | Pass --force to the drain: it also deletes each pod that no controller owns. Only a person gives it. |
| `--path` | `path` | - | The folder of the checkout. Default: the path of the entry, else <repos.base_dir>/\<owner\>/\<name\>. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

### `devops infra node reboot`

**Drain the node of each host, reboot the host with an Ansible ad-hoc task, wait for Ready with a new boot and the GPUs of before, uncordon only a node that was schedulable before, and wait for the health gate. The report shows the kernel before and after. An agent needs the agent access level full and host key checks on.**

```bash
devops infra node reboot [OPTIONS] <repo> <hosts>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo>` | `string` | Yes | The infra repo: owner/name, or the folder of a checkout, which its remote origin names. |
| `<hosts>` | `string` | Yes | The inventory hosts, in the order to run them. Each must be a host in service. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--force` | `boolean` | - | Pass --force to the drain: it also deletes each pod that no controller owns. Only a person gives it. |
| `--path` | `path` | - | The folder of the checkout. Default: the path of the entry, else <repos.base_dir>/\<owner\>/\<name\>. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

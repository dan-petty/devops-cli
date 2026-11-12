# `devops infra`

Manage an infra repo: a git repository with an Ansible inventory, its playbooks and roles. The settings name each infra repo and its agent access level (infra.repos).

## Commands

## `devops infra onboard`

**Check an Ansible infra repo for what devops infra needs, and print one row for each check with its state and the next step. The check fetches origin and reads the head of the default branch, not the working tree of the checkout, with local tool output only. With --confirm, write the entry of the repo in infra.repos, at agent access none unless a person gives --agent-access.**

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

**Run a playbook of an infra repo in check mode with diffs on its hosts in service, and show for each host the changed tasks, the disruptive changes (reboot, service-restart:\<unit\>, drain), the changes with the diff hidden and the tasks that check mode skipped. The run exports a commit that origin holds, by default the head of the default branch, never the working tree. It changes no host. The plan record and the runner artifacts stay in <data dir>/infra/\<owner\>/\<name\>/plans/\<id\>/. An agent needs the agent access level plan or above.**

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

**Apply a saved plan of devops infra plan to the hosts of an infra repo. The apply needs the plan id and the playbook, limit and tags of the plan, a plan not older than infra.plan_max_age_hours, a commit that origin holds and a healthy cluster. The hosts with no disruptive change run together. Each disruptive host runs alone in plan order: drain check, drain, a fresh check that must equal the plan, the run, Ready with the GPUs of before, the health of the nodes, uncordon only when the node was schedulable before, and no critical alert. The drain waits for the longest grace period of a pod of the node, and the apply names each workload that is down while the node is cordoned, because only that node can mount its volume. A change that the plan does not show, or the first failure, stops the apply. Each apply writes an audit record. An agent needs the agent access level safe for a plan with no disruptive change and no unchecked task, else full; an agent applies only a commit of the default branch, or at full the head of an open pull request, and only with host key checks on. An agent runs the command as one plain command: the project allow rule Bash(uv run devops *) lets it start, and the owner keeps that rule. A compound shell line (an assignment, ;, &&, |) goes to the auto-mode classifier. The agent access level of the repo is the real control.**

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

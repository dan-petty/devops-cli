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

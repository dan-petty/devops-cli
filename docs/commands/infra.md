# `devops infra`

Manage an infra repo: a git repository with an Ansible inventory, its playbooks and roles. The settings name each infra repo and its agent access level (infra.repos).

## Commands

## `devops infra onboard`

**Check an Ansible infra repo for what devops infra needs, from local files and local tool output only, and print one row for each check with its state and the next step. With --confirm, write the entry of the repo in infra.repos, at agent access none unless a person gives --agent-access.**

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

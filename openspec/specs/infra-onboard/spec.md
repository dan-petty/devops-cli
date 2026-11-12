# infra-onboard Specification

## Purpose
How `devops infra onboard` checks an Ansible infra repo for what `devops infra` needs, from local files and local tool output only, and how it writes the entry of the repo, with its agent access level, into `infra.repos`.

## Requirements

### Requirement: A repo entry with no level is at none
An entry of `infra.repos` SHALL hold operational keys only: `repo`, `path`, `kube_context`, `ssh_key_prefix` and `agent_access`. An entry with no `agent_access` SHALL read as `none`. An entry SHALL name its repository as owner/name, and two entries MUST NOT name one repository. A fact of the repository MUST NOT be a key of the entry.

#### Scenario: An entry with only its repository
- **WHEN** the settings hold `infra.repos: [{repo: example-org/infra}]`
- **THEN** the entry has `agent_access` `none`, `ssh_key_prefix` `ansible`, no `kube_context` and no `path`

#### Scenario: A project fact in the entry
- **WHEN** an entry of `infra.repos` holds `k8s_dir`
- **THEN** the settings are refused

#### Scenario: One repository in two spellings
- **WHEN** `infra.repos` names `example-org/infra` and `Example-Org/Infra`
- **THEN** the settings are refused

### Requirement: One row for each check
`devops infra onboard <repo>` SHALL print one row for each of 17 checks, in order, each with one state: `present`, `missing`, `not readable` or `listed`. It SHALL read only local files and the output of local commands: the project profile of the checkout, `ansible-config dump` and `ansible-inventory -i <inventory of the profile> --list` in the checkout, `ssh-keygen -F` for each host in service, and `kubectl config get-contexts`. It SHALL exit 1 when a row is `missing`.

#### Scenario: A complete repo
- **WHEN** the command checks a repo in the shape of dan-petty/homelab that holds every item and has an entry in `infra.repos`
- **THEN** each of the 17 rows is `present`, and the profile row lists each value of the profile with its source

#### Scenario: A repo that lacks one item
- **WHEN** the repo lacks a project type, `ansible.cfg`, its hosts, the group `offline`, its playbooks, its roles, a pinned collection, a CI workflow, the `devops ssh` key, the key of a host in `known_hosts`, the kube context or its entry, or turns host key checks off
- **THEN** the row of that item is `missing` and names the step that fixes it

#### Scenario: Items for a person to read
- **WHEN** the repository has no `.devops/project.toml`, a host in service sets no `devops_infra_node_service`, a task has `check_mode: false`, or the Makefile has a target `drain-<host>` or `rolling-restart`
- **THEN** the row of that item is `listed` with each value to declare and its source, host, task (`<path>:<line> <name>`) or target

#### Scenario: No tool environment
- **WHEN** no Ansible tool environment is installed: no install of `devops install-tools` and no `ansible-runner` on PATH
- **THEN** the first row is `missing` with the step `devops install-tools --tool ansible-core`, each row that needs the config or the inventory is `not readable`, and no Ansible command starts

### Requirement: Host key checks in the config and the inventory
The host key row SHALL be `missing` when the effective config sets `host_key_checking` false or holds `StrictHostKeyChecking=no` or `UserKnownHostsFile=/dev/null` in an option of the `ssh` plugin, or when a host variable `ansible_ssh_args`, `ansible_ssh_common_args`, `ansible_ssh_extra_args`, `ansible_host_key_checking` or `ansible_ssh_host_key_checking` does the same. It SHALL list each such setting.

#### Scenario: The inventory turns host key checks off
- **WHEN** every host sets `ansible_ssh_common_args: "-o StrictHostKeyChecking=no"`
- **THEN** the row lists `inventory: ansible_ssh_common_args StrictHostKeyChecking=no (6 hosts)`

### Requirement: The layout comes from the project profile
The command SHALL take the inventory, the playbook folder, the role folders and the group of hosts out of service from the project profile of the checkout, and MUST NOT read them from the settings.

#### Scenario: A project file names another playbook folder
- **WHEN** `.devops/project.toml` sets `[ansible] playbook_dir` to a folder with no playbook
- **THEN** the playbook row is `missing` and names that folder

### Requirement: Collections are the modules of plays and tasks
The collections row SHALL name the collections whose modules the plays, tasks, handlers and blocks call by their full name, and MUST NOT count a key of a variables mapping.

#### Scenario: Sysctl names in group variables
- **WHEN** `group_vars/all.yaml` holds a mapping with the keys `net.ipv4.ip_forward` and `fs.inotify.max_user_watches`
- **THEN** the row names only `ansible.posix`, `community.general` and `kubernetes.core`

### Requirement: Only a person raises the access level
The command SHALL refuse `--agent-access` `plan`, `safe` or `full` from an agent caller (an agent tool that `detect_agent` names, an MCP call or a process in a pod) with the error code `INFRA_ACCESS_REFUSED` and exit 1, before it starts a process or writes a file. The message SHALL name the setting `infra.repos[].agent_access`.

#### Scenario: An agent gives full
- **WHEN** an agent runs `devops infra onboard <repo> --agent-access full --confirm`
- **THEN** the command exits 1, names `infra.repos[].agent_access`, starts no process and leaves every byte of the config file

### Requirement: Confirm writes the entry
With `--confirm`, the command SHALL write the entry of the repository into `infra.repos` of the active config file, in place of an entry of the same repository. A new entry SHALL be at `none` unless a person gives `--agent-access`. With no `--agent-access`, an entry SHALL keep its level. The entry SHALL hold `path` only when the checkout is not `<repos.base_dir>/<owner>/<name>`.

#### Scenario: A person confirms a new entry
- **WHEN** a person runs the command with `--confirm` and no `--agent-access`
- **THEN** the config file holds the entry at `agent_access: none`, and the last row is `present` and names the file

#### Scenario: An agent confirms an entry at full
- **WHEN** an agent runs the command with `--confirm` and no `--agent-access` on an entry at `full`
- **THEN** the entry stays at `full`

### Requirement: A checkout names its repository
When `<repo>` is not `owner/name`, the command SHALL read it as the folder of a checkout and SHALL name the repository by the remote `origin` of that checkout.

#### Scenario: A local folder
- **WHEN** the command runs with the folder of a checkout whose `origin` is `https://github.com/example/service.git`, with `--confirm`
- **THEN** the entry names `example/service` and holds the folder as its `path`

### Requirement: A dry run starts nothing
With `--dry-run`, the command SHALL start no process and write no file, and SHALL print the commands and the write that a real run makes, in order.

#### Scenario: A dry run with confirm
- **WHEN** the command runs with `--confirm --dry-run`
- **THEN** no process starts, the config file keeps every byte, and the output lists the config dump, the inventory listing, `ssh-keygen -F <host>` for each host in service, the kubeconfig contexts and the write of `infra.repos`

### Requirement: One pinned Ansible environment
The tools lock SHALL hold `[python.ansible-core]`: one environment with ansible-core and ansible-runner from hashed requirements. Only `ansible-runner` SHALL go on PATH. The command SHALL start the Ansible commands from the environment that `devops install-tools` installed, else from the folder of the `ansible-runner` on PATH.

#### Scenario: The lock is read
- **WHEN** the packaged tools lock is read
- **THEN** `ansible-core` is a Python tool, its requirements pin `ansible-runner==2.4.3`, and its only command is `ansible-runner`

# infra-onboard Specification

## Purpose
How `devops infra onboard` checks an Ansible infra repo for what `devops infra` needs, from the files of its default branch, local tool output and the roles of its pinned collections, and how it writes the entry of the repo, with its agent access level, into `infra.repos`.

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
`devops infra onboard <repo>` SHALL print one row for each of 17 checks, in order, each with one state: `present`, `missing`, `not readable` or `listed`. It SHALL read the export of the default branch at `origin` and the output of local tools, in the order of the scenario "The requests of a complete repo". The fetch of `origin` and the install of the pinned collections SHALL be its only requests. It SHALL exit 1 when a row is `missing`.

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
- **WHEN** no `ansible-runner` is on PATH
- **THEN** the first row is `missing` with a step that names the upstream install page of ansible-runner, each row that needs the config or the inventory is `not readable`, and no Ansible command starts

#### Scenario: A tool environment on PATH
- **WHEN** an `ansible-runner` is on PATH
- **THEN** the first row is `present` and names the folder of the `ansible-runner` on PATH

#### Scenario: The requests of a complete repo
- **WHEN** the command checks the complete repo, whose `collections/requirements.yml` pins 3 collections
- **THEN** the commands are the git reads of the default branch, the config dump, the inventory listing, the install of the pinned collections, the role listing, `ssh-keygen -F` for each host in service and the kubeconfig contexts, in that order

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
- **THEN** no process starts, the config file keeps every byte, and the output lists the fetch of `origin`, the reads of the default branch and of the checkout, the export, the config dump, the inventory listing, the install of the pinned collections, the role listing, `ssh-keygen -F <host>` for each host in service, the kubeconfig contexts and the write of `infra.repos`

### Requirement: The report reads the default branch at origin
The command SHALL read the infra repo at the head of its default branch at `origin`, never in its working tree. It SHALL fetch `origin` with no prompt and no credential `-c` value: git gets the credential from its configured helper, `gh auth git-credential` in the devcontainer and the images. It SHALL export the tracked files of the commit that `refs/remotes/origin/HEAD` names into a new private folder, read the repo there, and remove it. It MUST NOT change a file or a branch of the checkout.

#### Scenario: The checkout is on an old branch
- **WHEN** the checkout is on the branch `feat/old`, which has no collections file and no CI workflow, and `origin/main` holds both
- **THEN** each of the 17 rows is `present`, and the Ansible commands ran in a folder outside the checkout that no longer exists

#### Scenario: No default branch is recorded
- **WHEN** the checkout has no `refs/remotes/origin/HEAD` after the fetch
- **THEN** the command exits 1 with the error code `INFRA_READ_FAILED`, names the step `git -C <checkout> remote set-head origin --auto`, and starts no Ansible command

#### Scenario: The fetch fails
- **WHEN** `git fetch` exits 128 with a token in its error text
- **THEN** the command exits 1 with the error code `INFRA_READ_FAILED`, names `git fetch --quiet origin` and git's reason with the token masked, and starts no other command

### Requirement: The report names the commit that it read
The command SHALL print the default branch and the commit that it read under the title. When the checkout is at another commit, it SHALL print one more line that names the branch of the checkout, or a detached HEAD, and its commit.

#### Scenario: A checkout on another branch
- **WHEN** the checkout is on the branch `feat/old` at another commit than `origin/main`
- **THEN** the two lines under the title name `origin/main` with its commit, and the branch `feat/old` with its commit

### Requirement: The export stays in its folder
The unpack of the export SHALL refuse a member that links out of its folder, a device and a write bit for the group or others.

#### Scenario: The export holds a link out of the folder
- **WHEN** the tar file of the commit holds `ansible.cfg` as a link to a file outside the folder
- **THEN** the command exits 1 with the error code `INFRA_READ_FAILED`, starts no Ansible command, and removes the folder

### Requirement: A relative repos base dir resolves under the main worktree
`default_checkout` SHALL resolve a relative `repos.base_dir` under `main_worktree_root()`, so every git worktree of devops-cli finds the clone at the main checkout. An absolute `repos.base_dir` SHALL stay as given.

#### Scenario: A command in a linked worktree
- **WHEN** `devops infra status owner/name` runs in a worktree, and `repos.base_dir` is `repos`
- **THEN** the default checkout is `<main worktree>/repos/owner/name`

#### Scenario: An absolute base dir
- **WHEN** `repos.base_dir` is `/srv/repos`
- **THEN** the default checkout is `/srv/repos/owner/name`

### Requirement: The Ansible environment is the ansible-runner on PATH
Only `ansible-runner` SHALL go on PATH. The command SHALL start the Ansible commands from the folder of the file that the `ansible-runner` on PATH resolves to. It SHALL look in no other folder and SHALL record no version of the environment.

#### Scenario: A link on PATH
- **WHEN** the `ansible-runner` on PATH is a link to a file in another folder
- **THEN** the command starts `ansible-config` from the folder of that file

#### Scenario: No ansible-runner on PATH
- **WHEN** no `ansible-runner` is on PATH
- **THEN** the command finds no tool environment, and a dry run shows each Ansible command with no folder

### Requirement: The roles row lists the roles of the pinned collections
When the export holds `collections/requirements.yml`, the command SHALL install its collections into a new temporary folder with `ansible-galaxy collection install`, read `ansible-doc -t role -l -j` with only that folder as the collections path, and remove the folder. The roles row SHALL list the roles of the role folders, then each role of the listing that names a collection, by its full name. The command MUST NOT read the files of a collection itself.

#### Scenario: A role of a pinned collection
- **WHEN** `collections/requirements.yml` pins the collection `example.infra`, whose role `nvidia` has an argument spec
- **THEN** the roles row is `present` and lists the 5 roles of `ansible/roles`, then `example.infra.nvidia`, `ansible-doc` ran with `ANSIBLE_COLLECTIONS_PATH` set to the `-p` folder of the install and `ANSIBLE_COLLECTIONS_SCAN_SYS_PATH` set to `False`, and the folder no longer exists

### Requirement: The roles row keeps the role folders when the collections do not read
When no Ansible tool environment is installed, or its folder holds no `ansible-doc`, the command SHALL start no install, and the roles row SHALL list the roles of the role folders and say in its reason that it does not list the roles of the pinned collections. When the install or the listing fails, the row SHALL list the roles of the role folders and name the command, its exit code and its last line in its reason.

#### Scenario: No ansible-doc in the tool environment
- **WHEN** the folder of the `ansible-runner` on PATH holds no `ansible-doc`
- **THEN** the roles row is `present` and lists the 5 roles of `ansible/roles`, its reason says that no `ansible-doc` is in the Ansible tool environment, and no `ansible-galaxy` or `ansible-doc` starts

#### Scenario: The install fails
- **WHEN** `ansible-galaxy collection install` exits 1
- **THEN** the roles row is `present` and lists the 5 roles of `ansible/roles`, its reason names `ansible-galaxy collection install` and the exit code 1, and no `ansible-doc` starts

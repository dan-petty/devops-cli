## ADDED Requirements

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

## MODIFIED Requirements

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

### Requirement: A dry run starts nothing
With `--dry-run`, the command SHALL start no process and write no file, and SHALL print the commands and the write that a real run makes, in order.

#### Scenario: A dry run with confirm
- **WHEN** the command runs with `--confirm --dry-run`
- **THEN** no process starts, the config file keeps every byte, and the output lists the fetch of `origin`, the reads of the default branch and of the checkout, the export, the config dump, the inventory listing, the install of the pinned collections, the role listing, `ssh-keygen -F <host>` for each host in service, the kubeconfig contexts and the write of `infra.repos`

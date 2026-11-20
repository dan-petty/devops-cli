## MODIFIED Requirements

### Requirement: One row for each check
`devops infra onboard <repo>` SHALL print one row for each of 17 checks, in order, each with one state: `present`, `missing`, `not readable` or `listed`. It SHALL read the export of the default branch at `origin`, with `ansible-config dump` and `ansible-inventory --list` in the export, `ssh-keygen -F` for each host in service and `kubectl config get-contexts`. The fetch of `origin` SHALL be its only request. It SHALL exit 1 when a row is `missing`.

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

## REMOVED Requirements

### Requirement: One pinned Ansible environment
**Reason**: The tools lock and `devops install-tools` are gone (#4363), so no pinned Ansible environment exists.
**Migration**: The command takes the Ansible environment of the `ansible-runner` on PATH, such as the one of the devtools image.

## ADDED Requirements

### Requirement: The Ansible environment is the ansible-runner on PATH
Only `ansible-runner` SHALL go on PATH. The command SHALL start the Ansible commands from the folder of the file that the `ansible-runner` on PATH resolves to. It SHALL look in no other folder and SHALL record no version of the environment.

#### Scenario: A link on PATH
- **WHEN** the `ansible-runner` on PATH is a link to a file in another folder
- **THEN** the command starts `ansible-config` from the folder of that file

#### Scenario: No ansible-runner on PATH
- **WHEN** no `ansible-runner` is on PATH
- **THEN** the command finds no tool environment, and a dry run shows each Ansible command with no folder

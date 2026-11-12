## ADDED Requirements

### Requirement: The report reads the default branch at origin
The command SHALL read the infra repo at the head of its default branch at `origin`, never in the working tree of the checkout. It SHALL fetch `origin` with the credential of the GitHub session and no prompt, export the tracked files of the commit that `refs/remotes/origin/HEAD` names into a new private folder, run every read of the repo there, and remove the folder after. It MUST NOT change a file or a branch of the checkout.

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
- **WHEN** no Ansible tool environment is installed: no install of `devops install-tools` and no `ansible-runner` on PATH
- **THEN** the first row is `missing` with the step `devops install-tools --tool ansible-core`, each row that needs the config or the inventory is `not readable`, and no Ansible command starts

### Requirement: A dry run starts nothing
With `--dry-run`, the command SHALL start no process and write no file, and SHALL print the commands and the write that a real run makes, in order.

#### Scenario: A dry run with confirm
- **WHEN** the command runs with `--confirm --dry-run`
- **THEN** no process starts, the config file keeps every byte, and the output lists the fetch of `origin`, the reads of the default branch and of the checkout, the export, the config dump, the inventory listing, `ssh-keygen -F <host>` for each host in service, the kubeconfig contexts and the write of `infra.repos`

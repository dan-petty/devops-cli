# infra-plan Specification

## Purpose
How `devops infra plan` runs a playbook of an infra repo in check mode at one commit that `origin` holds, shows for each host the changed tasks, the disruptive classes, the unchecked tasks and the hidden diffs, and keeps the plan record whose id the apply checks.

## Requirements

### Requirement: The plan reads one commit of origin
`devops infra plan <repo> <playbook>` SHALL export the tracked files of one commit that `origin` holds, by default the head of the default branch, with `--ref` a branch of `origin` or `pull/<number>/head`, into the project folder of a new private data folder under `<data dir>/infra/<owner>/<name>/plans/` with mode 0700. It MUST NOT read the working tree of the checkout.

#### Scenario: The head of a pull request
- **WHEN** a person plans with `--ref pull/19/head`
- **THEN** the command fetches `refs/pull/19/head` from `origin`, exports the commit of `FETCH_HEAD`, and the plan records the ref `pull/19/head` and that commit

#### Scenario: A branch that origin does not hold
- **WHEN** a person plans with `--ref no-such-branch` and `origin` holds no such branch
- **THEN** the command exits 1, names the ref, and exports nothing

### Requirement: The plan runs the playbook in check mode
The command SHALL run `ansible-runner run` with `--check --diff -v`, the inventory of the profile, `--tags` when given, the key of `devops ssh` as `ansible_ssh_private_key_file`, the repo's `ansible.cfg` and host key checks on. Before the run it SHALL install the pinned collections of `collections/requirements.yml` once for each version of that file.

#### Scenario: The run options
- **WHEN** a person plans `ansible/playbooks/03_k3s.yaml` with `--limit node-5.example.com --tags k3s`
- **THEN** `ansible-galaxy collection install` runs before `ansible-runner`, and `ansible-runner` gets `--playbook ansible/playbooks/03_k3s.yaml`, `--limit node-5.example.com:!offline`, the command line `--check --diff -v -i ansible/inventory/hosts.yaml --tags k3s -e ansible_ssh_private_key_file=<key>` and `ANSIBLE_HOST_KEY_CHECKING=True`

#### Scenario: The collections install once
- **WHEN** a person plans twice at the same commit
- **THEN** `ansible-galaxy` runs once and `ansible-runner` runs twice

#### Scenario: A playbook outside the repo
- **WHEN** a person plans `../outside.yaml`
- **THEN** the command exits 1, says that it is not a playbook file of the infra repo, and starts no `ansible-runner`

### Requirement: No host of the offline group is in the limit
The host pattern of the run SHALL be the `--limit`, else `all`, followed by `:!<offline group>` when the profile names a group of hosts out of service.

#### Scenario: A limit that names an offline host
- **WHEN** the limit is `node-5.example.com` and the offline group is `offline`
- **THEN** the host pattern is `node-5.example.com:!offline`

### Requirement: The plan of each host comes from the job events
The command SHALL read `artifacts/<ident>/job_events/*.json` in counter order and give, for each host, sorted: the changed tasks with their name, their path from the repo root and their action; the unchecked tasks; the failed tasks that the task does not ignore, and an unreachable host; and the disruptive classes of the changes.

#### Scenario: The k3s agent role
- **WHEN** the recorded run of the k3s agent role changes the agent config template with `diff: false` and the `systemd` task with the rendered state `restarted`, and reads the join token with `no_log`
- **THEN** the host has exactly two changes, the template with the diff hidden and the `systemd` task, and the disruptive class `service-restart:k3s-agent`

#### Scenario: A reboot
- **WHEN** the recorded run of node-2 runs `ansible.builtin.reboot`
- **THEN** node-2 has the disruptive class `reboot`

### Requirement: Hidden diffs and unchecked tasks
A change SHALL have its diff hidden when its result holds an empty diff (`diff: false`) or is censored (`no_log`). A `no_log` result SHALL count as a change only when the stats of the host count more changes than the other results show. A skipped task or loop item SHALL be unchecked, except when its skip result names a false `when` item (`false_condition`) that does not name `ansible_check_mode`.

#### Scenario: Changes, skips and a handler
- **WHEN** the recorded run of node-1 changes a template with a diff, a copy with `diff: false` and a `no_log` copy that the stats count, skips a `command` in check mode and a `command` with a false `when`, and runs the notified restart handler
- **THEN** node-1 has four changes, the copy and the `no_log` copy with the diff hidden, one unchecked `command`, and the disruptive class `service-restart:demo`

#### Scenario: A skip by a when that names check mode
- **WHEN** the recorded run of node-5 changes a copy, skips a `command` by `when: not (ansible_check_mode and demo_source is changed)`, skips one item of a loop by a `when` that names `ansible_check_mode`, and skips a `command` whose first false `when` item is `demo_restart_due | default(false)`
- **THEN** node-5 has one change, and the `command` and the loop are unchecked, but the last `command` is not

### Requirement: The disruptive classes
A changed `ansible.builtin.reboot` SHALL be `reboot`. A changed `kubernetes.core.k8s_drain` with the state `drain` SHALL be `drain`. A changed `systemd`, `systemd_service` or `service` task with the state `restarted`, `reloaded` or `stopped` SHALL be `service-restart:<unit>`, unless the host variable `devops_infra_nondisruptive_units` lists the unit. A service result with no arguments SHALL be disruptive, and a templated list of units SHALL list no unit.

#### Scenario: A unit that does not disrupt the host
- **WHEN** node-1 sets `devops_infra_nondisruptive_units: [demo]`
- **THEN** the restart of `demo` is a change of node-1 with no disruptive class

#### Scenario: A start and a cordon
- **WHEN** a changed `systemd_service` task has the state `started`, or a changed `k8s_drain` task has the state `cordon`
- **THEN** the change has no disruptive class

### Requirement: The plan record and its id
The command SHALL save `plan.json` with the repo, the ref, the commit, the playbook, the limit, the host pattern, the tags, the ansible-core version, the inventory hash, the status, the error and the plan of each host, in `plans/<id>/` with the runner artifacts, and remove the export. The id SHALL be the SHA-256 of the canonical JSON of these facts, without the time, the runner ident and the folder.

#### Scenario: The same events
- **WHEN** the same recorded events give two plans at the same commit and limit
- **THEN** both plans have the same id

#### Scenario: Another commit or limit
- **WHEN** two plans differ only in the commit or in the limit
- **THEN** their ids differ

### Requirement: A failed run is a failed plan
A failed task, an unreachable host, a run that passed its time limit or a run that ended with another status than `successful` SHALL mark the plan `failed`, and the command SHALL keep its record and exit 1.

#### Scenario: A failed task
- **WHEN** the recorded run fails a task on node-4
- **THEN** the plan is `failed`, node-4 names the task and its message, the record is saved, and the command exits 1

### Requirement: An agent needs the level plan
An agent caller SHALL be refused with the error code `INFRA_ACCESS_REFUSED` when the agent access level of the repo is below `plan`, before any process starts.

#### Scenario: An agent on a repo at none
- **WHEN** an agent plans on a repo at `none`
- **THEN** the command exits 1, names the level `plan` and the setting `infra.repos[].agent_access`, and starts no process

### Requirement: Output formats and the dry run
The command SHALL print a title, the commit that it read, a table of hosts, a table of tasks and the plan id with `--format table`, the default, and the plan model with `--format json` or `yaml`. With `--dry-run` it SHALL start no process, also for an agent on a repo at `none`, and SHALL list the git commands of the read, the inventory listing, the collection install, the `ansible-runner` run and the write of the record.

#### Scenario: A dry run of a branch
- **WHEN** an agent runs the command with `--ref fix/k3s --dry-run` on a repo at `none`
- **THEN** the command exits 0, starts no process, and lists the requests in order

### Requirement: The run output has no color
Every `ansible-runner` run of a playbook, the plan, the fresh check and the run of an apply, SHALL get `ANSIBLE_NOCOLOR=True` and `ANSIBLE_FORCE_COLOR=False` in its environment, also when the repo's `ansible.cfg` sets `force_color`, so the event text and the plan of a host are the same in a color terminal and with no terminal. A skip result that does not read as JSON, such as a result with color codes, SHALL stay unchecked.

#### Scenario: The environment of the plan run
- **WHEN** a person plans `ansible/playbooks/03_k3s.yaml`
- **THEN** `ansible-runner` gets `ANSIBLE_NOCOLOR=True` and `ANSIBLE_FORCE_COLOR=False`

#### Scenario: A plan with no terminal and its apply in a color terminal
- **WHEN** a person plans node-3 with no `TERM`, and applies the plan with `TERM=xterm-256color`
- **THEN** each `ansible-runner` run gets `ANSIBLE_NOCOLOR=True` and `ANSIBLE_FORCE_COLOR=False`, the fresh check of node-3 equals the plan, and the apply exits 0

#### Scenario: A skip result in color
- **WHEN** the recorded run in a color terminal skips a task of node-1 and a task of node-3 by a false `when`, with the color codes around the text of each skip
- **THEN** each of the two tasks is unchecked, and the rest of the plan of each host equals the plan of the run with no terminal

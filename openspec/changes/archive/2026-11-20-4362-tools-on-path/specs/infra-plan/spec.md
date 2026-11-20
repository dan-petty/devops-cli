## MODIFIED Requirements

### Requirement: The plan record and its id
The command SHALL save `plan.json` with the repo, the ref, the commit, the playbook, the limit, the host pattern, the tags, the inventory hash, the status, the error and the plan of each host, in `plans/<id>/` with the runner artifacts, and remove the export. The id SHALL be the SHA-256 of the canonical JSON of these facts, without the time, the runner ident and the folder. The record SHALL hold no version of the Ansible tool environment.

#### Scenario: The same events
- **WHEN** the same recorded events give two plans at the same commit and limit
- **THEN** both plans have the same id

#### Scenario: Another commit or limit
- **WHEN** two plans differ only in the commit or in the limit
- **THEN** their ids differ

#### Scenario: The record holds no tool version
- **WHEN** `devops infra plan` saves a plan
- **THEN** `plan.json` has no `ansible_core` field

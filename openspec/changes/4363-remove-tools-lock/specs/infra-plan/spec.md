## MODIFIED Requirements

### Requirement: The plan record and its id
The command SHALL save `plan.json` with the repo, the ref, the commit, the playbook, the limit, the host pattern, the tags, the inventory hash, the status, the error and the plan of each host, in `plans/<id>/` with the runner artifacts, and remove the export. The id SHALL be the SHA-256 of the canonical JSON of these facts, without the time, the runner ident and the folder. The record SHALL hold no version of the Ansible tool environment, and a record with a field that the model does not name SHALL NOT read.

#### Scenario: The same events
- **WHEN** the same recorded events give two plans at the same commit and limit
- **THEN** both plans have the same id

#### Scenario: Another commit or limit
- **WHEN** two plans differ only in the commit or in the limit
- **THEN** their ids differ

#### Scenario: A record from before #4363
- **WHEN** `devops infra apply` names a plan whose record holds the field `ansible_core`, as a plan of the pinned install did
- **THEN** the apply refuses the record, says to plan again, and runs no host

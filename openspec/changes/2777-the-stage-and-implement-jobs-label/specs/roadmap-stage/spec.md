## ADDED Requirements

### Requirement: Stage job labels its draft pull request from the title
The stage job SHALL add the `type/*` and `scope/*` labels that the title of its draft pull request gives, after the pull request opens.

#### Scenario: The title gives a type and a scope
- **WHEN** The stage job opens the draft pull request and the title gives a declared `type/*` label and a declared `scope/*` label
- **THEN** The pull request carries both labels

#### Scenario: The label call fails
- **WHEN** The label call on the open pull request returns an error
- **THEN** The job comment on the item records the label failure, the remote branch still exists and the job marks remain set

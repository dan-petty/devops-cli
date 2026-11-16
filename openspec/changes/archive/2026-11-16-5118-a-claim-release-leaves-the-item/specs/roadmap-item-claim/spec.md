## ADDED Requirements

### Requirement: A claim records the Status it replaces
The claim of an agent SHALL record the Status that the Item held before the claim under the record key `claim.replaced_status`, in the same write that sets In Progress.

#### Scenario: A claim of a Planned Item
- **WHEN** An agent claims an open Item that holds `status/planned`, and the claim sets In Progress.
- **THEN** The job record holds `Planned` under `claim.replaced_status` and the Item holds `status/in-progress`.

#### Scenario: A claim of an Item with no Status
- **WHEN** An agent claims an open Item that holds no `status/*` label, and the claim sets In Progress.
- **THEN** The job record holds no `claim.replaced_status` and the Item holds `status/in-progress`.

### Requirement: A release of an agent claim restores the Status
`devops roadmap release <issue>` SHALL write the Status that the facts of the Item give after it clears an `owner/agent` claim of an open Item whose Status label and job record both hold In Progress: Planned when the plan is merged, In Progress while a Job holds the Item or an open pull request names it, and Ready otherwise.

#### Scenario: A released Planned Item
- **WHEN** An Item holds `status/planned` with no owner, no Job and no open pull request, an agent claims it and a person releases the claim.
- **THEN** The Item holds no `owner/*` label and `status/planned`, and the start check of `devops roadmap implement` returns without raising.

#### Scenario: A released Item with no merged plan
- **WHEN** An Item holds In Progress from an agent claim, its plan is not merged, no Job holds it and no open pull request names it, and a person releases the claim.
- **THEN** The Item holds `status/ready` and no `owner/*` label.

#### Scenario: A released Item with an open pull request
- **WHEN** An Item holds In Progress from an agent claim and an open pull request names it, and a person releases the claim.
- **THEN** The Item holds `status/in-progress` and no `owner/*` label.

#### Scenario: A released Item with a running Job
- **WHEN** An Item holds In Progress from an agent claim and a Job holds it, and a person releases the claim.
- **THEN** The Item holds `status/in-progress` and no `owner/*` label.

### Requirement: A release keeps a Status that a job did not set
`devops roadmap release <issue>` MUST NOT write the Status of a closed issue, of an Item whose label is not In Progress, or of an Item whose job record does not hold In Progress.

#### Scenario: A Blocked Item
- **WHEN** An Item holds `status/blocked` with a stop of the implement job on record and an `owner/agent` claim, and a person releases the claim.
- **THEN** The Item holds `status/blocked` and no `owner/*` label.

#### Scenario: A Status that a person set
- **WHEN** An Item holds `status/in-progress`, its job record holds no In Progress Status, and a person releases an `owner/agent` claim.
- **THEN** The Item holds `status/in-progress` and no `owner/*` label.

#### Scenario: A closed issue
- **WHEN** A closed issue holds a stray `owner/agent` label and `status/planned`, and a person releases it.
- **THEN** The issue holds no `owner/*` label, still holds `status/planned`, and the store records no Status write.

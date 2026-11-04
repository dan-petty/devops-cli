## MODIFIED Requirements

### Requirement: A new runner image clears a stop of a retry class
A round SHALL clear the stop of an item that the Service set Blocked, and that no Job and no agent or person holds, when the digest in the template of CronJob `devops-cli-runner` differs from `implement.job_digest` and the class in `implement.failure` has the action `retry` in `ACTION_BY_CLASS`. A clear SHALL remove `implement.stopped`, set the Status to Ready or Planned, and comment the rule and both digests.

#### Scenario: The digest changed
- **WHEN** an item is Blocked with class `provider` and `implement.job_digest` A and the template names digest B
- **THEN** the round removes `implement.stopped`, sets the Status to Ready, records the class `provider` and the digest B in `implement.digest_clears`, comments the digest rule with A and B, and creates a Job that records B

#### Scenario: The digest is the same
- **WHEN** an item is Blocked with `implement.job_digest` A and the template names A, and ten rounds run
- **THEN** the item stays Blocked and the API receives no Job create

#### Scenario: A second stop on the new digest
- **WHEN** the Job that the digest rule started stops the item and the template still names B
- **THEN** the item stays Blocked and later rounds create no Job

#### Scenario: A stop with no digest on record
- **WHEN** an item is Blocked with `implement.stopped` and no `implement.job_digest`
- **THEN** the digest rule does not clear it

### Requirement: The job takes the highest priority first
A run SHALL take the items that the filter names with the highest priority first. Among equal priorities it SHALL take an item with no entry in `implement.digest_clears` before an item with one, and then the lowest issue number first. An item with no priority SHALL go last.

#### Scenario: Priority order
- **WHEN** the roadmap holds a Staged Ready P3 item and a Staged Ready P0 item, both of low effort
- **THEN** the plan selects the P0 item first

#### Scenario: A new item before a retried item
- **WHEN** two items of one priority are eligible, the lower number has an entry in `implement.digest_clears`, and the higher number has none
- **THEN** the plan selects the higher number first

#### Scenario: Priority before attempt state
- **WHEN** an item of priority P1 has an entry in `implement.digest_clears` and an item of priority P2 has none
- **THEN** the plan selects the P1 item first

## ADDED Requirements

### Requirement: A clear by digest keeps its record and stays within limits
A clear by digest SHALL append the class, the new digest and the time to `implement.digest_clears`. A stop with no class on record, or with a class of another action, SHALL stay Blocked. The round SHALL NOT clear by digest when the entries for the class reach `roadmap.implement.digest_clears_per_class` (default 1) or the entries of the item reach `roadmap.implement.digest_clears_per_item` (default 3), and SHALL read no content of the runner image.

#### Scenario: A class that a new image cannot fix
- **WHEN** an item is Blocked with class `plan_defect`, `refused_tool`, `premise_false` or `test`, and the template names a new digest
- **THEN** the item stays Blocked, the round reads no template for it, and `implement: retry` still clears it

#### Scenario: A stop with no class
- **WHEN** an item is Blocked with a digest on record and no `implement.failure`, and the template names a new digest
- **THEN** the digest rule does not clear it

#### Scenario: The class limit
- **WHEN** an item is Blocked with class `ci_infra`, `implement.digest_clears` holds one entry of class `ci_infra`, and the template names a new digest
- **THEN** the item stays Blocked until a trusted `implement: retry`

#### Scenario: A second retry class
- **WHEN** an item is Blocked with class `timeout`, `implement.digest_clears` holds one entry of class `provider`, and the template names a new digest
- **THEN** the round clears the stop and the list holds two entries

#### Scenario: The item limit
- **WHEN** an item is Blocked with class `provider`, `implement.digest_clears` holds three entries of other classes, and the template names a new digest
- **THEN** the item stays Blocked until a trusted `implement: retry`

#### Scenario: A record that does not parse
- **WHEN** `implement.digest_clears` is not a valid list
- **THEN** the digest rule does not clear the stop and `implement: retry` still does

### Requirement: A clear by digest writes one comment in a day
The round SHALL write no comment for a clear by digest on an item when `implement.digest_clear_commented_at` is less than 24 hours old, and SHALL still record the clear.

#### Scenario: One clear comment in a day
- **WHEN** a digest clear of an item runs less than 24 hours after `implement.digest_clear_commented_at`
- **THEN** the round clears the stop, records the entry, and writes no comment

#### Scenario: A clear comment after a day
- **WHEN** a digest clear of an item runs 24 hours or more after `implement.digest_clear_commented_at`
- **THEN** the round writes the comment and sets the time to now

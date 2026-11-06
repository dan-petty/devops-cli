## ADDED Requirements

### Requirement: The Service continues a Job that ended without a result
A round SHALL clear the stop of an item with the rule `continue` when `implement.stopped` is `job`, the class in `implement.failure` has the action `retry` in `ACTION_BY_CLASS`, and `implement.continuations` is less than `roadmap.implement.continuations_per_item`. A clear SHALL remove `implement.stopped`, `implement.failure` and the failed check, and set the Status to Ready or Planned.

#### Scenario: A Job that was killed
- **WHEN** the Job of an item ended Failed with no result, its log shows no known cause, and `implement.continuations` is not set
- **THEN** the round reports the Job and sets `implement.stopped` to `job` and the class to `ci_infra`
- **AND** the round clears the stop by the rule `continue` and makes a new Job for the same item that takes the branch from `origin`

#### Scenario: A Job that the Service ended by its stall
- **WHEN** the Service ended a Job by its stall and the report gives the class `timeout`
- **THEN** the round continues the item

#### Scenario: A Job that no longer exists
- **WHEN** the record of an item names a Job that the API does not list
- **THEN** the round reports the state `gone` and continues the item

#### Scenario: A class that a new attempt cannot fix
- **WHEN** the log of the Job that ended with no result shows an out-of-memory kill, so the class is `oom` with the action `raise_limit`
- **THEN** the item stays Blocked, `implement.continuations` is not set, and the API receives no Job create until a comment `implement: retry`

#### Scenario: An out-of-memory kill that the log does not show
- **WHEN** a Job ends with no result and its log holds no sign of a memory limit
- **THEN** the class is `ci_infra` and the round continues the item, because the Service reads no pod status

#### Scenario: A stop that the runner wrote
- **WHEN** an item is Blocked with `implement.stopped` as `group 1` and the class `provider`
- **THEN** the rule `continue` does not clear it

### Requirement: The continuations of an item are a setting
The setting `roadmap.implement.continuations_per_item` SHALL default to 2, SHALL refuse a count below 0, and SHALL turn the rule `continue` off at 0.

#### Scenario: The default
- **WHEN** no config file and no variable set the value
- **THEN** `roadmap.implement.continuations_per_item` is 2

#### Scenario: The limit is 0
- **WHEN** `roadmap.implement.continuations_per_item` is 0 and the Job of an item ends with no result
- **THEN** the item stays Blocked and the API receives no Job create

#### Scenario: A negative count
- **WHEN** the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_CONTINUATIONS_PER_ITEM` is -1
- **THEN** the load of the settings fails with an error that says the value must be greater than or equal to 0

### Requirement: A continuation is counted
A continuation SHALL set `implement.continuations` to the old count plus 1. The record SHALL hold a count and no other data. The count SHALL stay after a clear, and a comment `implement: retry` SHALL NOT reset it.

#### Scenario: No continuation is left
- **WHEN** a Job with a continuation count of 2 ends with no result, and ten rounds run
- **THEN** the item stays Blocked with `implement.stopped` as `job` and the API receives no Job create
- **AND** a comment `implement: retry` of the owner still clears the stop

#### Scenario: A new image at the limit
- **WHEN** the continuation count is at the limit and the template names a digest that differs from `implement.job_digest`
- **THEN** the rule `digest` clears the stop within its own limits, and `implement.continuations` is unchanged

#### Scenario: A count that is not a count
- **WHEN** `implement.continuations` holds `two`, `-1` or `1.5`
- **THEN** the rule `continue` does not clear the stop, the round does not fail, and a comment `implement: retry` still clears the stop

### Requirement: The comment of a continuation says how many are used
The comment of a continuation SHALL name the rule, the Job and the class, and SHALL say "continuation n of N". At the last continuation it SHALL also say "No continuation is left".

#### Scenario: The first continuation
- **WHEN** the rule `continue` clears a stop and `implement.continuations` is not set
- **THEN** `implement.continuations` is 1, the comment says "continuation 1 of 2", and the comment does not say "No continuation is left"

#### Scenario: The last continuation
- **WHEN** a Job with a continuation count of 1 ends with no result and its class has the action `retry`
- **THEN** the round records `implement.continuations` as 2, comments "continuation 2 of 2" and "No continuation is left", and makes a new Job

### Requirement: A continuation spends no clear by digest
The rule `continue` SHALL run before the rule `digest`, SHALL read no template and SHALL add no entry to `implement.digest_clears`.

#### Scenario: A continuation and a new image
- **WHEN** a Job ends with no result and the template names a new digest
- **THEN** the round clears the stop by the rule `continue`, `implement.digest_clears` is not set, and the new Job records the new digest in `implement.job_digest`

### Requirement: The report of a Job with no result says what the Service does next
The report of a Job with no result SHALL say that the Service starts a new Job when a retry can fix the class of the stop. It SHALL name the setting `roadmap.implement.continuations_per_item` and the comment `implement: retry`. It SHALL say that a new runner image also clears the stop within its limits.

#### Scenario: A Job that failed
- **WHEN** the round reports a Job that ended Failed and left its item In Progress
- **THEN** the comment names the setting `roadmap.implement.continuations_per_item` and the comment `implement: retry`

## MODIFIED Requirements

### Requirement: A Job that leaves its item eligible stops the item
When a reported Job leaves its item neither In Review nor stopped, the round SHALL set the item Blocked and record `implement.stopped` as `job`. No Job SHALL be created for the item before a clear rule runs.

#### Scenario: A Job that failed
- **WHEN** the Job of an item has the condition Failed, the item is In Progress, and no continuation applies to it
- **THEN** the item gets a comment with the state `failed` and the tail of the log
- **AND** `implement.job_state` is `failed`, the Status is Blocked, and `implement.stopped` is `job`
- **AND** the next round creates no Job for the item

### Requirement: A new runner image clears a stop of a retry class
A round SHALL clear the stop of an item that the Service set Blocked, and that no Job and no agent or person holds. The digest in the template of CronJob `devops-cli-runner` must differ from `implement.job_digest`. The class in `implement.failure` must have the action `retry` in `ACTION_BY_CLASS`. A clear SHALL remove `implement.stopped`, set the Status to Ready or Planned, and comment the rule and both digests.

#### Scenario: The digest changed
- **WHEN** an item is Blocked with class `provider` and `implement.job_digest` A and the template names digest B
- **THEN** the round removes `implement.stopped` and sets the Status to Ready
- **AND** the round records the class `provider` and the digest B in `implement.digest_clears` and comments the digest rule with A and B
- **AND** the round creates a Job that records B

#### Scenario: The digest is the same
- **WHEN** an item is Blocked with `implement.job_digest` A and the template names A, no continuation applies, and ten rounds run
- **THEN** the item stays Blocked and the API receives no Job create

#### Scenario: A second stop on the new digest
- **WHEN** the Job that the digest rule started stops the item, no continuation applies, and the template still names B
- **THEN** the item stays Blocked and later rounds create no Job

#### Scenario: A stop with no digest on record
- **WHEN** an item is Blocked with `implement.stopped` and no `implement.job_digest`
- **THEN** the digest rule does not clear it

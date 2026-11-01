# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: A stopped item goes back to Ready and is never retried`
- TO: `### Requirement: A stopped item is Blocked and the job does not retry it`

## MODIFIED Requirements

### Requirement: A stopped item is Blocked and the job does not retry it
When a step, the rebase, the documentation, the archive, a push or the checks stop the item, the job SHALL post a comment that starts with the marker and names the step, the reason and the last message of the agent, SHALL set Status to Blocked, and SHALL record `implement.stopped` with the step. It SHALL push the commits of the steps that passed. The job SHALL NOT run the item again until a clear rule removes the record. The job SHALL go on to the next selected item.

#### Scenario: A step stops
- **WHEN** the step of group 2 reports stopped
- **THEN** Status is Blocked, `implement.stopped` is `group 2`, the comment holds the reason, `origin` holds the commit of group 1, and the pull request is still a draft

#### Scenario: A conflict on the rebase before a push
- **WHEN** the default branch gains a change that conflicts with the branch after the last group, or after the fix step
- **THEN** the job aborts the rebase, `origin` holds the commits that passed, Status is Blocked, and `implement.stopped` is `push`

### Requirement: A Job that leaves its item eligible stops the item
When a reported Job leaves its item neither In Review nor stopped, the round SHALL set the Status of the item to Blocked and record `implement.stopped` as `job`, so that no Job is created for the item before a clear rule runs.

#### Scenario: A Job that failed
- **WHEN** the Job of an item has the condition Failed and the item is In Progress
- **THEN** the item gets a comment with the state `failed` and the tail of the log, `implement.job_state` is `failed`, the Status is Blocked, `implement.stopped` is `job`, and the next round creates no Job for the item

### Requirement: A Planned item gets a draft pull request at its first push
The job SHALL push the branch of a Planned item with `-u origin` when it first holds a commit past the default branch, and SHALL open a draft pull request into the default branch at once. The first body SHALL hold no closing keyword. The job SHALL record the branch and the pull request, and then go on as it does for a Staged item. A stop before the first commit SHALL push nothing.

#### Scenario: A stop in the first group
- **WHEN** the step of group 1 reports stopped before any commit
- **THEN** `origin` holds no branch for the item, no pull request opened, the Status is Blocked, and `implement.stopped` is `group 1`

#### Scenario: A stop in the second group
- **WHEN** the step of group 2 reports stopped after group 1 passed
- **THEN** `origin` holds the new branch with the commit of group 1, a draft pull request is open with a body that has no closing keyword, and the record holds its number

#### Scenario: A retry
- **WHEN** a comment `implement: retry` follows that stop
- **THEN** the plan selects the item with the recorded branch and pull request as a Staged item, and the run takes the branch over

#### Scenario: A draft that GitHub refuses
- **WHEN** GitHub refuses the draft pull request after the push
- **THEN** the job removes the branch from `origin`, stops the item, and the record holds no pull request

### Requirement: The Job is recorded before it is created
The round SHALL record the name of the Job in `implement.job` and the digest of the runner image in the template of CronJob `devops-cli-runner` in `implement.job_digest`, and clear `implement.job_state`, before it creates the Job. A create that fails SHALL remove the record of the Job. So a Job that no record names does not exist, and an item whose Job dies early is reported and stopped.

#### Scenario: The order
- **WHEN** a round creates the Job for item 1
- **THEN** the record of item 1 holds the name and the digest when the API receives the create

#### Scenario: A refused create
- **WHEN** the API refuses the create
- **THEN** the round raises `ClusterJobError` and the record of the item holds no Job

## ADDED Requirements

### Requirement: A new runner image clears a stop one time
A round SHALL clear the stop of an item that the Service set Blocked, and that no Job and no agent or person holds, when the digest in the template of CronJob `devops-cli-runner` differs from `implement.job_digest`. A clear SHALL remove `implement.stopped`, set the Status to Ready or Planned, and post a comment that names the rule and both digests. A stop with no digest on record SHALL stay Blocked. The round SHALL clear a stop at most one time for each digest.

#### Scenario: The digest changed
- **WHEN** an item is Blocked with `implement.job_digest` A and the template names digest B
- **THEN** the round removes `implement.stopped`, sets the Status to Ready, comments the digest rule with A and B, and creates a Job that records B

#### Scenario: The digest is the same
- **WHEN** an item is Blocked with `implement.job_digest` A and the template names A, and ten rounds run
- **THEN** the item stays Blocked and the API receives no Job create

#### Scenario: A second stop on the new digest
- **WHEN** the Job that the digest rule started stops the item and the template still names B
- **THEN** the item stays Blocked and later rounds create no Job

#### Scenario: A stop with no digest on record
- **WHEN** an item is Blocked with `implement.stopped` and no `implement.job_digest`
- **THEN** the digest rule does not clear it

### Requirement: A retry from a person clears a stop at once
A comment `implement: retry` of the owner, a member or a collaborator, made after the last comment of the job, SHALL clear the stop of a Blocked item in the next round, whatever the digest. The comment of the Service SHALL name the retry rule.

#### Scenario: A retry on the same digest
- **WHEN** an item is Blocked and its digest is unchanged, and the owner comments `implement: retry`
- **THEN** the round clears the stop, comments the retry rule, and creates a Job

#### Scenario: A retry from a stranger
- **WHEN** a user who is not the owner, a member or a collaborator comments `implement: retry`
- **THEN** the item stays Blocked

### Requirement: The report of a Job names its image digest
The comment that reports a Job that ended SHALL name `implement.job_digest` when the record holds it.

#### Scenario: A Job that failed
- **WHEN** the round reports a Job whose record holds a digest
- **THEN** the comment names that digest

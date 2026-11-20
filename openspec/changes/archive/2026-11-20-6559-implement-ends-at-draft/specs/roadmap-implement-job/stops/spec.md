## MODIFIED Requirements

### Requirement: The job writes how its run ended
The job SHALL write `implement.result` as the last mark of the write that ends each run of an item. The value SHALL be `drafted` for a run that ended at the draft pull request, `stopped` for a stop, `yielded` for a claim, and `returned` for a return to New. The job SHALL clear the key in its first record write of a run.

#### Scenario: A run that a claim ended
- **WHEN** a person claims the item while group 1 runs
- **THEN** the record holds `implement.result` equal to `yielded`

#### Scenario: A run that stops
- **WHEN** the scoped checks stop the item
- **THEN** the record holds `implement.result` equal to `stopped`, written after `implement.stopped`

#### Scenario: A stale result
- **WHEN** a new Job starts on an item whose record holds `implement.result` equal to `drafted`, and the Job is killed in its first group
- **THEN** the record holds no `implement.result`

### Requirement: The comment on the pull request lists each amendment with its evidence
The comment of the job on the pull request SHALL show one line for each applied amendment and each split: the group, the kind, the defect, the evidence, and the old and the new text. A stopped item whose pull request exists SHALL get the same lines in a comment.

#### Scenario: An amended run
- **WHEN** the job applied an amendment and reaches the draft pull request
- **THEN** the comment on the pull request holds a line with the group, the kind, the defect, the evidence, `old` and `new`

#### Scenario: A stop after an amendment
- **WHEN** the job applied an amendment and a later step stops the item, and the pull request exists
- **THEN** the pull request gets a comment with the line of the amendment

### Requirement: The job checks the premise of every open behavior group before the first step
The job SHALL check the premise of each open behavior group once in a run, at the first group boundary, after the claim check and before the first step. An open group has a task that is not ticked. The check SHALL read the head of the checkout at that boundary. A later group boundary of the run SHALL make no premise check. The comment of the return SHALL say that the run made no model request and wrote no code.

#### Scenario: A false premise of a late group
- **WHEN** a plan has 3 groups, behavior group 3 adds a guard that the branch defines, and groups 1 and 2 are open
- **THEN** the job returns the item to New before the step of group 1: it makes no model request, pushes no checkpoint, closes no pull request, and the comment names the guard and says that the run made no model request

#### Scenario: A guard of a group that passed in an earlier Job
- **WHEN** an earlier Job passed behavior group 1, which added `_delivery_title`, and group 2 is open
- **THEN** the job checks no premise of group 1, runs group 2, and ends the run at the draft

## Purpose

The update that a subscribed webhook event of the roadmap runs at once, scoped to what its delivery carries, and the record that keeps the reconciling poll from doing that update again or from skipping a change that it did not handle.

## ADDED Requirements

### Requirement: An issues delivery runs intake of its one issue
`run_scoped_update` SHALL run intake of the one issue that a delivery of the `issues` event with the action `opened`, `edited` or `reopened` names, on the model lane, with intake's own decision code. It SHALL decide and write nothing for another issue.

#### Scenario: A delivery about one of three candidates
- **WHEN** a delivery of `issues` with the action `opened`, `edited` or `reopened` names candidate 2 of three candidates
- **THEN** the model judges candidate 2 alone, and only candidate 2 gets labels and a reason comment

#### Scenario: An edit of an issue that is already an Item
- **WHEN** a delivery of `issues` `edited` names an issue that holds a `priority/*` label, and no other candidate is open
- **THEN** the model judges nothing, the store records no write, and no intake record is written

### Requirement: An event with no scoped update stays a hint
`run_scoped_update` SHALL return None for an event or an action that has no row in `SCOPED_UPDATES`, and SHALL do nothing.

#### Scenario: A closed issue and an opened pull request
- **WHEN** a delivery of `issues` `closed`, or of `pull_request` `opened`, is given
- **THEN** `run_scoped_update` returns None and the store records no write

### Requirement: A scoped update writes no last success
A scoped update SHALL write no job's last success to `schedule.json`.

#### Scenario: Scoped intake after an earlier intake round
- **WHEN** intake's last success is half an hour old and a delivery of `issues` `opened` runs its scoped update
- **THEN** `schedule.json` holds the same last success for intake as before

### Requirement: The reconciling poll decides a lost delivery and not a handled one
After a scoped intake, the next poll SHALL run intake when another fresh candidate is open, also before intake's hourly interval. That intake SHALL decide the other candidate and SHALL not decide the issue of the scoped update again.

#### Scenario: One delivered and one lost event
- **WHEN** the delivery of candidate 2 runs its scoped update, the delivery of candidate 1 (`opened` or `reopened`) is lost, and a poll comes five minutes later, before intake's interval
- **THEN** the poll runs intake, the model judges candidate 1, and the model judged candidate 2 only once, in the scoped update

### Requirement: A scoped update keeps the record that a capped round left
Scoped intake SHALL add the issue that it decided to the intake record, SHALL keep every other entry, and SHALL keep intake due when the record was due.

#### Scenario: A scoped update after a capped round
- **WHEN** a round decides five of seven candidates and leaves a fresh one, and a delivery of candidate 6 runs its scoped update
- **THEN** the record holds the entries of candidates 1 to 6 and stays due, and the next poll decides candidate 7 alone

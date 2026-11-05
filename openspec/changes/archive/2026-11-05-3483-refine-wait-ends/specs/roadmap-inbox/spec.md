## MODIFIED Requirements

### Requirement: The inbox lists the gates of the jobs in order
`devops roadmap inbox` SHALL list, in this order: ready plan pull requests of the jobs, ready implementation pull requests of the jobs, the open release pull request, items in `status/blocked` with their cause, New items that wait on a person in refine, old claims, and labels that the repository lacks. A pull request is a job's when the job record of an open item names it in `implement.pr` or `stage.pr`; `implement.pr` wins. A draft pull request of a job SHALL NOT be listed.

#### Scenario: Each category
- **WHEN** the repository holds a ready plan pull request, a ready implementation pull request, a release pull request, a blocked item, a New item that waits on a person in refine, an old claim and a missing label
- **THEN** the output lists one line for each, in the order above

#### Scenario: A draft of a job
- **WHEN** the record of an item names a draft pull request in `stage.pr`
- **THEN** the output does not list it

#### Scenario: A staged branch that became an implementation
- **WHEN** one pull request is named by `stage.pr` and by `implement.pr` of an item
- **THEN** it is listed once, as an implementation pull request

#### Scenario: A pull request that a Job holds
- **WHEN** the record of an item names a ready pull request and a runner Job that no round reported
- **THEN** the output does not list the pull request

## ADDED Requirements

### Requirement: The inbox lists each New item that waits on a person in refine
`devops roadmap inbox` SHALL list one line for each open New item whose `refine.next_step` is `person`, and for each one whose `refine.returned_body_hash` equals its `refine.body_hash`. The line SHALL show the number, the age, the cause and the step that clears it. The read SHALL use the job record of the open issues only.

#### Scenario: A question for a person
- **WHEN** an open New item records `refine.next_step` as `person`
- **THEN** the output lists one line for it, in the section "New items that wait on a person in refine"

#### Scenario: Two returns on the same body
- **WHEN** an open New item records `refine.returned_body_hash` equal to `refine.body_hash`
- **THEN** the output lists one line that says that the stage job returned it twice on the same body

#### Scenario: An item that waits on nothing in refine
- **WHEN** an item records `refine.next_step` as `ready` or `blocked`, is Ready, or is closed
- **THEN** the output lists no refine line for it

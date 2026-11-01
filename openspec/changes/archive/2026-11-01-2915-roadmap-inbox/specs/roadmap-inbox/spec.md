# roadmap-inbox Specification

## Purpose
How `devops roadmap inbox` lists what waits for a person on the roadmap: the pull requests of the jobs at their gates, the release pull request, blocked items, old claims and repository state, each with its age and the one step that clears it.

## ADDED Requirements

### Requirement: The inbox lists the gates of the jobs in order
`devops roadmap inbox` SHALL list, in this order: ready plan pull requests of the jobs, ready implementation pull requests of the jobs, the open release pull request, items in `status/blocked` with their cause, old claims, and labels that the repository lacks. A pull request is a job's when the job record of an open item names it in `implement.pr` or `stage.pr`; `implement.pr` wins. A draft pull request of a job SHALL NOT be listed.

#### Scenario: Each category
- **WHEN** the repository holds a ready plan pull request, a ready implementation pull request, a release pull request, a blocked item, an old claim and a missing label
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

### Requirement: Each line has the number, the age and one clearing step
Each line SHALL show the number of its issue or pull request (`-` when it has none), the time since its last update, and the one command or action that clears it. A pull request of a job SHALL be cleared by a review and a merge at its gate, the release pull request by a merge, a stopped item by the comment `implement: retry`, an old claim by `devops roadmap release`, and missing labels by `devops gh labels sync`.

#### Scenario: The command of a line
- **WHEN** the inbox lists an old claim of #7 and missing labels
- **THEN** the claim line shows `#7`, an age, and `devops roadmap release 7 --confirm`, and the labels line shows `devops gh labels sync`

#### Scenario: The cause of a block
- **WHEN** a blocked item records `implement.stopped` as `group 2`
- **THEN** its line shows `group 2` as the cause and the retry comment as the step

### Requirement: Old claims are shown, never removed
A claim SHALL be old when its issue and every open pull request whose head branch names the issue (`<type>/<issue>-<slug>`) have not changed for `CONST_ROADMAP_INBOX_CLAIM_DAYS` days. The inbox SHALL write nothing, so no claim is released.

#### Scenario: A pull request keeps a claim young
- **WHEN** an item holds `owner/agent` and its issue is 10 days old, and the pull request `feat/7-x` changed 1 day ago
- **THEN** the inbox lists no old claim for the item

#### Scenario: An idle claim
- **WHEN** an item holds `owner/human` and neither its issue nor any pull request changed for 8 days
- **THEN** the inbox lists the claim with an age of 8 days

### Requirement: Pull requests of people and agents are listed apart
Every open pull request that no job record names and that is not the release pull request SHALL be listed in a second list, after the first. A ready one SHALL be cleared by a review and a merge. A draft SHALL be shown as a draft, with `devops pr monitor` and `devops pr ready` as its step.

#### Scenario: A person's pull requests
- **WHEN** a person has one ready pull request and one draft, and a job has a ready plan pull request
- **THEN** the first list holds the plan pull request only, and the second list holds the two pull requests of the person, the draft marked as a draft

### Requirement: The inbox reads a bounded number of requests and writes none
The inbox SHALL read the open issues, the open pull requests, the repository labels and `.github/labels.yml` once, and the newest commit of that file only when the labels differ. It SHALL NOT call a model, and it SHALL write nothing to GitHub or git. Its dry-run class SHALL be `request-plan`: `--dry-run` SHALL make no request and SHALL list the reads.

#### Scenario: No write
- **WHEN** the inbox runs on a store that records writes
- **THEN** the store records no write

#### Scenario: The reads
- **WHEN** the inbox runs against a store that counts reads of open issues, open pull requests and labels
- **THEN** each is read once, and no read of every issue happens

#### Scenario: A dry run
- **WHEN** `inbox --dry-run` runs with processes and sockets refused
- **THEN** the exit status is 0, the output says that no request was made, and it lists the reads and no write

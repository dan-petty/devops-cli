# roadmap-inbox Specification

## Purpose
How `devops roadmap inbox` lists what waits for a person on the roadmap: the pull requests of the jobs at their gates, the release pull request, blocked items, old claims and repository state, each with its age and the one step that clears it.

## Requirements

### Requirement: The inbox lists the gates of the jobs in order
`devops roadmap inbox` SHALL list, in this order: ready plan pull requests of the jobs, ready implementation pull requests of the jobs, the open release pull request, items in `status/blocked` with their cause, New items that wait on a person in refine, New items with an unapplied split, New items with an alternatives question, drafts of jobs that are old or have a failed check, old claims, and labels that the repository lacks.
#### Scenario: Each category
- **WHEN** the repository holds a ready plan pull request, a ready implementation pull request, a release pull request, a blocked item, a New item that waits on a person in refine, a New item with an unapplied split, a New item with an alternatives question, an old draft of a job, an old claim and a missing label
- **THEN** the output lists one line for each, in the order above

### Requirement: The inbox lists each job pull request once
A pull request is a job's when the job record of an open item names it in `implement.pr` or `stage.pr`; `implement.pr` wins. A draft of a job SHALL be listed only as a draft line of the draft class.

#### Scenario: A draft of a job
- **WHEN** the record of an item names a draft pull request in `stage.pr`, and the draft is newer than `roadmap.inbox.draft_days` and has no failed check
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
- **THEN** the claim line shows `#7`, an age, and `devops roadmap release 7 --repo <repo> --confirm`, and the labels line shows `devops gh labels sync --repo <repo>`

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
The inbox SHALL read, for each repository it lists, the open issues, the open pull requests, the repository labels and `.github/labels.yml` once, and the newest commit of that file only when the labels differ. It SHALL read the check runs of the head commit of each open draft of a job, once for each draft. It SHALL NOT call a model, and it SHALL write nothing to GitHub or git. Its dry-run class SHALL be `request-plan`: `--dry-run` SHALL make no request and SHALL list the reads.

#### Scenario: No write
- **WHEN** the inbox runs on a store that records writes
- **THEN** the store records no write

#### Scenario: The reads
- **WHEN** the inbox runs against a store that counts reads of open issues, open pull requests and labels
- **THEN** each is read once for each repository, and no read of every issue happens

#### Scenario: A dry run
- **WHEN** `inbox --dry-run` runs with processes and sockets refused
- **THEN** the exit status is 0, the output says that no request was made, and it lists the reads and no write

### Requirement: A listing takes one request for each 100 rows
The inbox SHALL read each of its three listings, the open issues, the open pull requests and the repository labels, with one request for each 100 rows. A run for one repository SHALL send one request for each 100 open issues and pull requests, one for each 100 open pull requests, one for each 100 labels, one for `.github/labels.yml`, and one for the newest commit of that file when the labels differ. It SHALL send one request for the check runs of each open draft of a job.

#### Scenario: The requests of a run
- **WHEN** the plan of the inbox is read for one repository
- **THEN** it holds three listings that repeat for each page, one read of the labels file, one read of the newest commit of that file that only differing labels make, and one check-run read for each open draft of a job

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

### Requirement: The inbox states when the Planned limit holds
`devops roadmap inbox` SHALL list one line when the count of open Planned items is at the setting `roadmap.stage.planned_limit` or over it. The line SHALL name the count, the setting and the priorities that the stage job still plans, SHALL show `-` as its number and its age, and SHALL give a way to clear it: deliver Planned items, or raise the setting. The line SHALL come after the line of the labels. Under the limit, the inbox SHALL list no such line.

#### Scenario: At the limit
- **WHEN** 2 open items are Planned, 1 closed item is Planned, and the setting is 2
- **THEN** the output lists one line that names the count 2, `roadmap.stage.planned_limit` and `P0-Critical or P1-High`, with `-` as its number and age

#### Scenario: Under the limit
- **WHEN** 1 open item is Planned and the setting is 2
- **THEN** the output lists no such line

### Requirement: The inbox reads each repository of service.repos by default
Without `--repo`, `devops roadmap inbox` SHALL read each repository of the setting `service.repos`, in its order, and list the lines of each. With `--repo`, it SHALL read that repository only. When `service.repos` is empty and `--repo` is not given, the command SHALL fail with an error that names `service.repos`, and SHALL read no repository.

#### Scenario: No repository option
- **WHEN** `service.repos` names two repositories and `--repo` is not given
- **THEN** the command reads both repositories and lists the lines of each

#### Scenario: One repository option
- **WHEN** `--repo` names a repository
- **THEN** the command reads that repository only

#### Scenario: No repository configured
- **WHEN** `service.repos` is empty and `--repo` is not given
- **THEN** the command exits with status 1 and its error names `service.repos`

### Requirement: The inbox refuses a service.repos entry that is not owner/name
An entry of `service.repos` that is not `owner/name` SHALL fail `devops roadmap inbox` before any repository is read. The error SHALL name the entry and `service.repos`.

#### Scenario: An entry that is not owner/name
- **WHEN** `service.repos` holds an entry without `/`, such as `no-owner`
- **THEN** the command exits with status 1, its error names the entry and `service.repos`, and it reads no repository

### Requirement: The inbox lists each unapplied split and each alternatives question
`devops roadmap inbox` SHALL list one line for each open New item whose `refine.next_step` is `split`, and one line for each open New item whose `refine.alternatives_asked` is set. The split line SHALL show the step that clears it, which is to split the item as the refine comment proposes. The alternatives line SHALL name the covering tool that refine put to a person. An item MAY have one line of each class.

#### Scenario: An unapplied split
- **WHEN** an open New item records `refine.next_step` as `split`
- **THEN** the output lists one line for it, in the section of the split class, with the step that clears it

#### Scenario: An alternatives question
- **WHEN** an open New item records `refine.alternatives_asked` as the URL of a covering tool
- **THEN** the output lists one line for it that names the URL of the tool

#### Scenario: A closed item with a split
- **WHEN** a closed item records `refine.next_step` as `split`
- **THEN** the output lists no split line for it

### Requirement: The inbox lists a draft of a job that is old or has a failed check
`devops roadmap inbox` SHALL list one line, in the draft class, for each draft of a job that is older than `roadmap.inbox.draft_days` or whose head commit has a failed check run. A draft of a job that no runner Job holds is a draft of a job. A draft that is newer than the setting and has no failed check SHALL have no line.

#### Scenario: An old draft
- **WHEN** a draft of a job is older than `roadmap.inbox.draft_days`
- **THEN** the output lists one line for it, in the draft class

#### Scenario: A draft with a failed check
- **WHEN** a draft of a job that is newer than the setting has a failed check run on its head commit
- **THEN** the output lists one line for it, in the draft class, with the step that clears the failed check

#### Scenario: A draft that waits for its checks
- **WHEN** a draft of a job is newer than `roadmap.inbox.draft_days` and no check run failed
- **THEN** the output lists no line for it

### Requirement: The inbox states the age of each wait and the classes it holds
Each line whose age is over the setting `roadmap.inbox.wait_days` SHALL show a mark that the wait is over that number of days. After its title, the output SHALL start with the count of the lines of each class, before any line. The option `--kind` SHALL keep only the lines of the class it names, and the counts SHALL stay complete.

#### Scenario: An old wait
- **WHEN** a line is older than `roadmap.inbox.wait_days`
- **THEN** its line shows the mark with the number of days of the setting

#### Scenario: Counts by class
- **WHEN** the inbox lists lines of two classes
- **THEN** the output starts, after its title, with the count of each of the two classes

#### Scenario: The class filter
- **WHEN** `--kind` names one class
- **THEN** the output lists the lines of that class only, and the counts of all classes

## MODIFIED Requirements

### Requirement: The inbox lists the gates of the jobs in order
`devops roadmap inbox` SHALL list, in this order: ready plan pull requests of the jobs, ready implementation pull requests of the jobs, the open release pull request, items in `status/blocked` with their cause, New items that wait on a person in refine, New items with an unapplied split, New items with an alternatives question, drafts of jobs that are old or have a failed check, old claims, and labels that the repository lacks. A pull request is a job's when the job record of an open item names it in `implement.pr` or `stage.pr`; `implement.pr` wins. A draft of a job SHALL be listed only as a draft line of the draft class.

#### Scenario: Each category
- **WHEN** the repository holds a ready plan pull request, a ready implementation pull request, a release pull request, a blocked item, a New item that waits on a person in refine, a New item with an unapplied split, a New item with an alternatives question, an old draft of a job, an old claim and a missing label
- **THEN** the output lists one line for each, in the order above

#### Scenario: A draft of a job
- **WHEN** the record of an item names a draft pull request in `stage.pr`, and the draft is newer than `roadmap.inbox.draft_days` and has no failed check
- **THEN** the output does not list it

#### Scenario: A staged branch that became an implementation
- **WHEN** one pull request is named by `stage.pr` and by `implement.pr` of an item
- **THEN** it is listed once, as an implementation pull request

#### Scenario: A pull request that a Job holds
- **WHEN** the record of an item names a ready pull request and a runner Job that no round reported
- **THEN** the output does not list the pull request

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

## ADDED Requirements

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

### Requirement: The inbox lists each unapplied split and each alternatives question
`devops roadmap inbox` SHALL list one line for each open New item whose `refine.next_step` is `split`, and one line for each open New item whose `refine.alternatives_asked` is set. The split line SHALL show the step that clears it, which is to split the item as the refine comment proposes. The alternatives line SHALL name the covering tool that was put to a person. An item MAY have one line of each class.

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
Each line whose age is over the setting `roadmap.inbox.wait_days` SHALL show a mark that the wait is over that number of days. The output SHALL start with the count of the lines of each class, before any line. The option `--kind` SHALL keep only the lines of the class it names, and the counts SHALL stay complete.

#### Scenario: An old wait
- **WHEN** a line is older than `roadmap.inbox.wait_days`
- **THEN** its line shows the mark with the number of days of the setting

#### Scenario: Counts by class
- **WHEN** the inbox lists lines of two classes
- **THEN** the output starts with the count of each of the two classes

#### Scenario: The class filter
- **WHEN** `--kind` names one class
- **THEN** the output lists the lines of that class only, and the counts of all classes

## REMOVED Requirements

### Requirement: The next-step comment names the cited files
**Reason**: The refine section of the body holds the watched files, and a comment holds no content of the section (#6196).
**Migration**: The requirement "The refine section holds the result of the round" of `roadmap-refine/comments` holds the files under `### Watched files`, and the event line names that part.

## MODIFIED Requirements

### Requirement: A wait on a person ends when a cause that its text names ends
Without `--item`, `devops roadmap refine` SHALL look again at an unchanged item that waits on a person when an issue that the wait text names closed, or a file that it names changed on the default branch, at or after the start of the wait. The wait text SHALL be the Open questions, Suspected block and Watched files of the refine section and the replies that the rounds read. An issue that closed before, an issue of another repository and the item SHALL end no wait.

#### Scenario: A named issue closes after the comment
- **WHEN** an item waits on a person, an open question of its refine section asks about #12, and #12 closes after refine's last comment
- **THEN** the next round refines the item again

#### Scenario: A named issue closed before the comment
- **WHEN** an open question of the refine section names #12 and #12 closed before refine's last comment
- **THEN** the item keeps waiting and the round makes no model call

#### Scenario: A named file changes with no recorded block path
- **WHEN** an item waits on a person with no `refine.block_paths`, an open question of its refine section names `src/sample.py`, and a commit on the default branch changes that file after refine's last comment
- **THEN** the next round refines the item again

#### Scenario: A reply names the issue
- **WHEN** the refine section names no issue, a reply that the round read names #12, and #12 closes after refine's last comment
- **THEN** the next round refines the item again

### Requirement: A read of the comments of a waiting item is recorded
When a round reads the comments of an item that waits and finds no reply, `--confirm` SHALL record `refine.comments_seen` (the count of the listing), `refine.commented_at` (the time of refine's last comment) and `refine.wait_refs` (the issues, then the paths, that the wait text names). A round that finds the same values in the record SHALL write nothing for the item.

#### Scenario: A wait on a person that names an issue and a path
- **WHEN** an item waits on a person, an open question of its refine section names issue 3 and the path `src/sample.py`, and a round runs with `--confirm`
- **THEN** the job record holds `refine.comments_seen` `1`, `refine.commented_at` with the time of refine's comment, and `refine.wait_refs` `#3,src/sample.py`

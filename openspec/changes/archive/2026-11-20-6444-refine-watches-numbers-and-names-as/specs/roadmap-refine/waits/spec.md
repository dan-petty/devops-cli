## MODIFIED Requirements

### Requirement: A wait on a person ends when a cause that its text names ends
Without `--item`, `devops roadmap refine` SHALL look again at an unchanged item that waits on a person when an issue that the wait text names closed, or a file that it names and the tree of the round holds changed on the default branch, at or after the start of the wait. The wait text SHALL be the Open questions, Suspected block and Watched files of the refine section and the replies that the rounds read. An issue that closed before, an issue of another repository and the item SHALL end no wait.

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
When a round reads the comments of an item that waits and finds no reply, `--confirm` SHALL record `refine.comments_seen` (the count of the listing), `refine.commented_at` (the time of refine's last comment) and `refine.wait_refs` (the issues, then the paths that the tree of the commit of the round holds, that the wait text names). A round that finds the same values in the record SHALL write nothing for the item.

#### Scenario: A wait on a person that names an issue and a path
- **WHEN** an item waits on a person, an open question of its refine section names issue 3 and the path `src/sample.py`, and a round runs with `--confirm`
- **THEN** the job record holds `refine.comments_seen` `1`, `refine.commented_at` with the time of refine's comment, and `refine.wait_refs` `#3,src/sample.py`

### Requirement: An unchanged waiting item costs no comment read
Without `--item`, a round SHALL read no comment of an item that waits on a blocker or on a person, whose body is unchanged, whose count of comments is the recorded `refine.comments_seen`, and whose recorded `refine.wait_refs` holds no path that the tree of the commit of the round lacks. The item SHALL keep waiting on its next step, and the round SHALL make no model call for it.

#### Scenario: A second round after the record
- **WHEN** an item waits on an open blocker, and a round has recorded the read of its comments
- **THEN** the next round lists the item as waiting on its blocker, reads no comment of the item and makes no model call

## ADDED Requirements

### Requirement: A wait records only the paths that the tree holds
A round SHALL record in `refine.wait_refs` only the paths that the tree of the commit it reads holds, as a file or as a directory that holds a tracked path.

#### Scenario: A decimal, a version, a dotted setting and a domain before two real files
- **WHEN** a wait text names `0.202`, `v1.37.2`, `ai.portkey_url` and `deps.dev` before two files that the tree holds, and `text_paths` reads the text with that tree
- **THEN** the round records the two files in `refine.wait_refs` and none of the four other values

### Requirement: The five-path cap counts only the paths that the tree holds
`text_paths` SHALL apply `CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS` after it drops the candidates that the tree does not hold, so the first five real paths take the slots.

#### Scenario: Six real files
- **WHEN** a wait text names six files that the tree holds, and `text_paths` reads it with that tree
- **THEN** the round records the first five files and drops the sixth

### Requirement: A path that a period or a comma follows is kept
The cited-path pattern SHALL accept a period or a comma after a path, so `text_paths` finds a file that ends a sentence.

#### Scenario: A sentence ends on a path
- **WHEN** a wait text names a file that the tree holds and a period or a comma follows the path, and `text_paths` reads it with that tree
- **THEN** the round records that file

### Requirement: A value that the tree does not hold costs no commits read
The wait check MUST read no commits for a candidate that the tree does not hold, because the round drops it before it writes `refine.wait_refs`.

#### Scenario: A decimal beside a real file
- **WHEN** a wait text names a decimal and a file that the tree holds, and `path_changed_at` reads each recorded path
- **THEN** the store reads the commits of the file and records no read of the decimal

### Requirement: A directory that the tree holds is a watched path
`text_paths` SHALL keep a directory of the tree as a watched path, because a commit changes the files under it.

#### Scenario: A directory that holds a file
- **WHEN** a wait text names a directory and the tree holds a file under that directory, and `text_paths` reads it with that tree
- **THEN** the round records the directory

### Requirement: The explain verdict reads the tree of the default branch
`devops roadmap explain` SHALL give `refine_left_out` the tracked paths of `origin/<default>`, which it fetched, so it gives the verdict that a round of the Service gives (#3483), whatever branch the clone holds.

#### Scenario: A person asks why an item waits
- **WHEN** a person runs `devops roadmap explain` on an item whose wait text names a real path and a decimal
- **THEN** the verdict reads the real path alone, through `refine_left_out`

#### Scenario: The clone holds another branch
- **WHEN** a wait names a file that `origin/main` holds and the `HEAD` of the clone does not, and a commit changed that file after the start of the wait
- **THEN** `devops roadmap explain` says that refine takes the item

### Requirement: Each path of a run of paths is kept
The cited-path pattern SHALL leave the separator after a path to the next path, so `text_paths` finds each path of a run of paths that one space each separates.

#### Scenario: Four paths in a row
- **WHEN** a wait text reads `Read a.py b.py c.py d.py` and `text_paths` reads it with no tree
- **THEN** `text_paths` gives `a.py`, `b.py`, `c.py` and `d.py`

### Requirement: A record that holds a path that the tree lacks is read again
A round SHALL read as not current a recorded `refine.wait_refs` that holds a path that the tree of its commit lacks. The round SHALL read the comments of the item once, record the references that the tree filter keeps, read no commits of a value that the tree lacks, and make no model call for an item that still waits.

#### Scenario: A record written before the tree filter
- **WHEN** an item waits on a person, its count of comments is the recorded `refine.comments_seen`, and its recorded `refine.wait_refs` is `0.202,src/sample.py`, which a round wrote before the tree filter
- **THEN** the next round records `refine.wait_refs` `src/sample.py`, reads no commits of `0.202` and makes no model call, and the round after it reads no comment of the item

### Requirement: A file that the tree of the round does not hold ends no wait
A round SHALL end no wait for a path of the wait text that the tree of its commit does not hold, so a file that a later commit creates, or that a commit deleted after the record, ends no wait. A person who expects such a file SHALL reply in a comment, which ends the wait.

#### Scenario: A named file that the tree does not hold
- **WHEN** an item waits on a person, an open question of its refine section names `src/sample.py`, the tree of the round does not hold that file, and a commit changes it after refine's last comment
- **THEN** the item keeps waiting and the round makes no model call

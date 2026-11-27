## ADDED Requirements

### Requirement: A stage round replaces the record of another issue
A stage round SHALL find, in its listing and with no request, each item whose body holds a record that was written for another issue. The round of `devops roadmap stage --confirm`, the stage row of the Service and a stage Job for its own item SHALL send one record write with no mark for each such item, before the removals of the round. A run that writes nothing SHALL list each such item under `## Records to replace` and SHALL send no write.

#### Scenario: Two rounds with an item that holds the record of another repository
- **WHEN** item 7 is open with Status New and its body holds a block with `stage.branch` `feat/4107-add-the-rows` and `stage.pr` and `stage.ready` `4110`, item 8 is open with Status New and its block holds `stage.branch` `fix/8-the-other-item` and `stage.pr` `12`, pull request 12 is an open draft on that branch, the repository holds no pull request 4110, and the round runs two times
- **THEN** no round has a failed item, no round reads pull request 4110, the body of item 7 holds no block after the first round, and the block of item 8 holds its keys as before

#### Scenario: The plan of a run
- **WHEN** an open item holds the record of another issue and `devops roadmap stage` plans a round with no writer
- **THEN** the plan lists the item under `## Records to replace`, and the body of the item holds its block as before

### Requirement: A recorded pull request is the plan of an item only on the recorded branch
The stage job SHALL take the number of `stage.pr` as the plan pull request of an item only when `stage.branch` names the item, and SHALL take a pull request as that plan only when its head branch is `stage.branch`. The read of the staged plans SHALL take the close of a pull request with no merge as a rejection only then, and SHALL send no read for a recorded number with no such branch.

#### Scenario: A pull request that closed with no merge on the recorded branch
- **WHEN** an open Ready item records `stage.branch` `fix/1-the-job-drops-a-comment` and a pull request that closed with no merge and whose head is that branch
- **THEN** the round finds the rejected plan of the item

#### Scenario: A pull request that closed with no merge on another branch
- **WHEN** an open Ready item records `stage.branch` `fix/1-the-job-drops-a-comment` and a pull request that closed with no merge and whose head is `feat/4107-add-the-rows`
- **THEN** the round finds no rejected plan, and the item keeps its Status

#### Scenario: A recorded number with no recorded branch
- **WHEN** an open Ready item records `stage.pr` and no `stage.branch`
- **THEN** the round reads no pull request for the item and has no failed item

### Requirement: The draft of a closed item is the open pull request on its staged branch
The cleanup of a closed item SHALL take the recorded number as the draft of the staged branch only when an open pull request of that number has the branch as its head. The round SHALL find that in its one read of the open pull requests.

#### Scenario: The draft of a closed item on the recorded branch
- **WHEN** an item is closed, its staged branch `fix/1-the-job-drops-a-comment` holds one commit by the session identity, and its record names an open pull request whose head is that branch
- **THEN** the job closes that pull request and deletes the branch

#### Scenario: A pull request on another branch is not the draft of a closed item
- **WHEN** an item is closed, its staged branch `fix/1-the-job-drops-a-comment` holds one commit by the session identity, and its record names an open pull request whose head is `feat/4107-add-the-rows`
- **THEN** the cleanup of the staged branch sends no request for that pull request

### Requirement: A recorded branch is the branch of an item only when it names the item
The stage job SHALL judge the branch of `stage.branch` of a closed item, and the branch of the intent mark `stage.pending` of an open item, only when the branch has the form `<type>/<issue>-<slug>` with the number of the item. A recorded branch that names no issue number or another issue number SHALL give no removal.

#### Scenario: The recorded branch of a closed item names no issue
- **WHEN** an item is closed, its record names the pushed branch `docs/release-notes` as `stage.branch`, and only the session identity wrote to that branch
- **THEN** the plan holds no removal for the item, and the round sends no write for the branch or the item

#### Scenario: The branch of an intent mark names no issue
- **WHEN** an open item holds an intent mark that is 1 day old and names the pushed branch `docs/release-notes`, and only the session identity wrote to that branch
- **THEN** the plan holds no removal for the item

#### Scenario: The branch of an intent mark names the item
- **WHEN** open item 1 holds an intent mark that is 1 day old and names the pushed branch `fix/1-the-job-drops-a-comment`, and only the session identity wrote to that branch
- **THEN** the round removes the orphan

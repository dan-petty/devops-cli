## ADDED Requirements

### Requirement: A plan pull request closed with no merge leaves a comment on the issue
In each run the job SHALL read the pull request that `stage.pr` names for each open New or Ready item whose plan is not on the default branch. For a pull request that is closed and not merged, the job SHALL post one comment on the issue with the marker of the stage job, the marker of a rejected plan, the number of the pull request and the reason. For an open or merged pull request it SHALL post none. With `--item` it SHALL read only the pull request of the named item.

#### Scenario: The pull request is merged or open
- **WHEN** the plan pull request of an item is merged, or is open
- **THEN** the job posts no comment on the issue and writes no `stage.rejected`

#### Scenario: The pull request closed with no merge
- **WHEN** the plan pull request of a Ready item is closed and not merged
- **THEN** the job posts one comment on the issue that holds both markers, the number of the pull request and the reason

#### Scenario: The item is named
- **WHEN** a person runs the job with `--item` for one item
- **THEN** the job reads the pull request of that item and of no other item

### Requirement: The reason is the last long comment of a person
The reason SHALL be the text of the last comment on the closed pull request that has more than `EVIDENCE_MIN_CHARS` characters, that a person with write access wrote, and that the Service bot did not write. The job SHALL mask secrets in the reason and cut it to `CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS` tokens. When no comment qualifies, the comment on the issue SHALL say that no comment gives a reason, and the job SHALL still record the rejection.

#### Scenario: The last comment is one word
- **WHEN** a closed plan pull request holds a long comment of the owner and then the comment `rejected` of the owner
- **THEN** the comment on the issue holds the long comment and not the word `rejected`

#### Scenario: The newest long comment is not a reason
- **WHEN** the newest long comment on a closed plan pull request was written by the Service bot or by an account with no write access
- **THEN** the comment on the issue holds the newest long comment of a person with write access

#### Scenario: No comment gives a reason
- **WHEN** a closed plan pull request holds only the comment `rejected` of the owner
- **THEN** the comment on the issue says that no comment gives a reason, and the job still records the rejection

#### Scenario: The reason holds a secret
- **WHEN** the last long comment holds a token
- **THEN** the comment on the issue holds the masked text

### Requirement: A rejected plan returns the item to New
After the comment, the job SHALL set the item to New when it is Ready, clear every key of the stage record, and write `stage.rejected` as JSON that holds the number of the pull request, the hash of the text of the item outside the refine section, the time at which the pull request closed, and the files that the reason names. The job SHALL make each write for one item in the order: the delete of the branch, the comment, the Status with the record.

#### Scenario: A Ready item with a rejected plan
- **WHEN** a Ready item has a plan pull request that closed with no merge
- **THEN** the item is New, its record holds no `stage.branch`, no `stage.pr` and no `stage.ready`, and `stage.rejected` holds the number of the pull request and the hash of its text

#### Scenario: A person already returned the item
- **WHEN** an item that is New has a plan pull request that closed with no merge
- **THEN** the job posts the comment and writes the record, and the Status stays New

### Requirement: A rejected plan loses its staged branch when only the Service wrote to it
For a rejected plan the job SHALL delete the staged branch of the record with the rule of a closed item: every commit of the branch past `origin/<default branch>` has the identity of the session as author or is a clean merge. When any other commit exists, the job SHALL keep the branch and say so in the plan. A branch that is gone needs no delete.

#### Scenario: Only the Service wrote to the branch
- **WHEN** a plan pull request closed with no merge and its branch holds one commit by the session identity
- **THEN** the job deletes the branch from `origin`, and the item is no longer held by a pushed branch

#### Scenario: A person added a commit
- **WHEN** a plan pull request closed with no merge and its branch holds a commit by another author
- **THEN** the job keeps the branch, the plan lists it with its reason, and the comment and the record are still written

### Requirement: The job leaves out an item whose plan was rejected until its text or a named file changes
The job SHALL leave out an item that holds a `stage.rejected` record, with a reason that names the pull request. The leave-out SHALL end when the hash of the text of the item outside the refine section differs from the recorded hash, or when a commit on the default branch changed a file of the record at or after the recorded time. The rule SHALL apply to the rejections that the same run finds. `--item` SHALL overrule the rule.

#### Scenario: Nothing changed
- **WHEN** an item is Ready again, holds a `stage.rejected` record, its text hashes as recorded and no named file changed
- **THEN** the job leaves it out and the reason names the pull request

#### Scenario: A person edits the text
- **WHEN** a person edits the body of that item, and the pushed branch of the rejected plan was deleted
- **THEN** the job takes the item and the branch of the closed pull request holds nothing

#### Scenario: A named file changes
- **WHEN** a commit on the default branch changed a file that the reason names, after the pull request closed
- **THEN** the job takes the item

#### Scenario: A refine round rewrites its section
- **WHEN** refine writes its section in the body and the text outside the section is the same
- **THEN** the job still leaves the item out

#### Scenario: The item is named
- **WHEN** a person runs the job with `--item` for that item
- **THEN** the job takes the item

#### Scenario: The same run finds the rejection
- **WHEN** a run finds a rejected plan whose branch a person deleted before the run
- **THEN** the run does not select the item

### Requirement: The plan request holds the reason of a rejected plan
The request of a plan call SHALL hold the key `rejected_plan` for an item whose record holds `stage.rejected`: the text of the newest comment that holds the marker of a rejected plan and that a trusted author wrote, without either marker and cut to `CONST_ROADMAP_REFINE_MAX_REPLY_TOKENS` tokens. A request for any other item SHALL hold no such key. The prompt SHALL say that the key holds the reason of a person and that the plan must not state again the premise that the reason shows to be false.

#### Scenario: An item that was rejected and then edited
- **WHEN** the job plans an item that holds `stage.rejected` after a person edited its body
- **THEN** the request holds `rejected_plan` with the reason and with no marker

#### Scenario: A named item whose rejection the same run finds
- **WHEN** a person runs the job with `--item` for an item whose plan pull request closed with no merge and the record has no `stage.rejected` yet
- **THEN** the request holds `rejected_plan` with the reason that the run copies to the issue

#### Scenario: An item that was never rejected
- **WHEN** the job plans an item with no `stage.rejected` record
- **THEN** the request holds no `rejected_plan` key

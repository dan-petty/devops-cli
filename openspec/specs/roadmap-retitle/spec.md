# roadmap-retitle Specification

## Purpose
How `devops roadmap retitle` and the guards around it keep the title summary of roadmap items within the limit of 60 characters, so that the stage job and the implement job do not leave out an item for its title.

## Requirements

### Requirement: Intake refuses a long summary
`devops roadmap intake --title` SHALL refuse a new candidate whose title has a Conventional Commit type and a summary longer than `SUMMARY_MAX_CHARS`, and SHALL write no issue.

#### Scenario: Intake with an over-limit summary
- **WHEN** a new candidate has a title with a summary of 61 characters
- **THEN** the command exits 1 with a message that names 61 and 60, and no issue is created

### Requirement: Dry run lists title changes
The title repair pass SHALL list each title it would change when it runs without `--confirm`, and SHALL write no title and no comment.

#### Scenario: Preview of an over-limit title
- **WHEN** the repair pass runs without `--confirm` on an open item with a 68-character summary
- **THEN** the output names the item and its new title, and the title of the item stays the same

### Requirement: Confirmed repair keeps type and scope
With `--confirm`, the repair pass SHALL replace only the summary of a title whose type is in `CONST_BRANCH_TYPES`, keep that type and the scope, and write a title that passes `title_problems`. It SHALL write one comment with the marker of the job. A title with an unlisted type gets the type of "Retitle corrects an unlisted title type".

#### Scenario: Confirmed repair
- **WHEN** the repair pass runs with `--confirm` on an item titled `fix(roadmap): ...` with a 68-character summary
- **THEN** the new title starts with `fix(roadmap): `, its summary has at most 60 characters, and `title_problems` returns no problem

### Requirement: Planned item uses its plan pull request title
For a Planned item, the repair pass SHALL take the summary from the title of the plan pull request that the job record names, and SHALL make no model request.

#### Scenario: Planned item with a valid plan title
- **WHEN** a Planned item has an over-limit title and its plan pull request title is `docs(openspec): plan #<issue> Add a title repair pass`
- **THEN** the new summary is `Add a title repair pass` and the model records no request

### Requirement: Planned item without a usable plan title is left
The repair pass SHALL leave a Planned item whose plan pull request title is missing or invalid, SHALL make no model request, and SHALL comment the reason once.

#### Scenario: Planned item without a usable plan title
- **WHEN** a Planned item has no plan pull request title that gives a valid summary, and the pass runs twice with `--confirm`
- **THEN** the title stays the same, the item holds one comment with the reason, and the model records no request

### Requirement: Item without a plan uses the model
For an item that is not Planned, the repair pass SHALL ask the model for a summary, SHALL ask once more with the faults of a reply that fails `title_problems`, and SHALL write only a title that passes `title_problems`.

#### Scenario: Valid reply after one fault
- **WHEN** the first reply of the model is longer than the limit and the second reply is valid
- **THEN** the new title uses the second reply and the model records two requests

#### Scenario: Two faulty replies
- **WHEN** both replies fail `title_problems`
- **THEN** the pass leaves the item and writes no comment

### Requirement: A person's edit is kept
The repair pass MUST NOT change a title that someone changed after the last comment of a job, or that someone changed when no job commented. It SHALL make no model request for such an item.

#### Scenario: Rename after the last job comment
- **WHEN** a person renames an item after the last job comment on it
- **THEN** the pass leaves the title and reports that it skipped the item

### Requirement: A changed title is not overwritten
The repair pass SHALL NOT write a title when the title of the item changed after the pass read it.

#### Scenario: Rename between plan and write
- **WHEN** a person renames an item after the pass planned its new title and before `--confirm` writes it
- **THEN** the pass writes nothing for that item

### Requirement: A run is bounded
The repair pass SHALL examine at most `--limit` items, the lowest numbers first, and SHALL report how many items with a long title wait.

#### Scenario: Limit of one
- **WHEN** two items have a long title and the limit is 1
- **THEN** the pass changes the lower-numbered item and the report counts one more item

### Requirement: Planned long title stops before model work
The implement job SHALL leave out a Planned item whose title summary is longer than `SUMMARY_MAX_CHARS`, before it reads the plan or makes a model request.

#### Scenario: Planned item with a long title
- **WHEN** the implement job judges a Planned item with a 70-character summary
- **THEN** the item is left out with the reason of the stage job, and no request is made

### Requirement: Inbox lists a long-titled item
`devops roadmap inbox` SHALL list a blocked open item even when its title summary is longer than `SUMMARY_MAX_CHARS`.

#### Scenario: Inbox with an over-limit title
- **WHEN** an open item has the status Blocked and a 70-character summary
- **THEN** the inbox output includes the item

### Requirement: A Service row runs the job
The model lane SHALL hold a row named `retitle` after `refine` and before `stage`, and `DEFAULT_DUE_TABLE` SHALL include it.

#### Scenario: Row order
- **WHEN** `MODEL_LANE_ROWS` is read.
- **THEN** it holds `retitle` between `refine` and `stage`, and `DEFAULT_DUE_TABLE` holds it too.

### Requirement: The row is due by its interval
The `retitle` row SHALL be due on its first run and when its last success is at least `DEFAULT_ROADMAP_RETITLE_INTERVAL_MINUTES` (61) old.

#### Scenario: Due at the interval
- **WHEN** the last success of the row is 61 minutes old, or the row has no success.
- **THEN** `run_due_jobs` lists `retitle` as due.

#### Scenario: Not due before the interval
- **WHEN** the last success of the row is 60 minutes old.
- **THEN** `run_due_jobs` does not list `retitle` as due.

### Requirement: The row plans and applies the retitle job
The `retitle` row SHALL call `plan_retitle` with the model of the retitle job and `limit=DEFAULT_ROADMAP_RETITLE_LIMIT`, then call `apply_retitle` with the plan it got, and SHALL need no clone.

#### Scenario: Row run
- **WHEN** the row runs on a store with an open item whose title summary is longer than 60 characters.
- **THEN** the item gets a title that passes `title_problems`, and the schedule records the success of `retitle`.

### Requirement: Stub table omits the row unless asked
`build_stub_table` SHALL omit the `retitle` row unless a `retitle` runner or `include_retitle=True` asks for it.

#### Scenario: Default stub table
- **WHEN** `build_stub_table()` runs with no `retitle` runner.
- **THEN** the table has no `retitle` row.

### Requirement: Skip mark
When the repair pass leaves an item with a long title, it SHALL write the mark `retitle.skipped` in the job record of the item, once, with one write. The value SHALL be a hash of the title, the body and the `stage.pr` mark that the decision read. This covers an item whose title a person changed, a Planned item without a usable plan title, and an item for which the model gave no summary that passes `title_problems` in two tries. The pass SHALL write no mark for an item that it retitles.

#### Scenario: The model gives no usable summary
- **WHEN** both replies of the model fail `title_problems` and the pass runs with `--confirm`
- **THEN** the job record of the item holds `retitle.skipped`, and the pass wrote that mark once

#### Scenario: A person changed the title
- **WHEN** a person renamed an item after the last job comment and the pass runs with `--confirm`
- **THEN** the job record of the item holds `retitle.skipped`

#### Scenario: The title is changed
- **WHEN** the pass retitles an item
- **THEN** the pass writes no `retitle.skipped` for it

### Requirement: A skipped item is not selected again
The selection of the repair pass SHALL leave out an open item whose `retitle.skipped` equals the hash of its current title, body and `stage.pr` mark. It SHALL select the item again when its title, its body or its `stage.pr` mark changes. A comment on the item SHALL NOT select it again. A skipped item SHALL NOT hold a place of `--limit`.

#### Scenario: Next round after a skip
- **WHEN** the pass skipped an item and runs again with no change to the item
- **THEN** the selection does not hold the item, and a later item with a long title takes the place of the limit

#### Scenario: The item changes
- **WHEN** the title, the body or the `stage.pr` mark of a skipped item changes
- **THEN** the selection holds the item again

### Requirement: A skipped item costs one write once
A skipped item SHALL cost one write in the round that skips it. In a later round with no change to the item, it SHALL cost no read of its comments, no read of its title changes, no read of a pull request title and no model request.

#### Scenario: Two rounds
- **WHEN** the pass runs twice with `--confirm` on one item that it cannot shorten
- **THEN** the first round makes one write of the mark and the second round makes no write, no read of the item and no model request

### Requirement: Dry run lists the write of the mark
The dry run of the repair pass SHALL list the write of the mark `retitle.skipped` with the condition under which it runs.

#### Scenario: Preview of the writes
- **WHEN** the repair pass runs with `--dry-run`
- **THEN** the planned writes hold one write of the body of an item with a condition for a skipped item

### Requirement: Retitle corrects an unlisted title type
The retitle job SHALL select an open item whose title type is not in `CONST_BRANCH_TYPES`, also when its summary is short. For a type that the correction table of `commit_title.py` maps, it SHALL write the mapped type and scope with the same summary and no model request, and one comment that names the old type and the types.

#### Scenario: A security title with a short summary
- **WHEN** the job runs with `--confirm` on an open item titled `security(ssh): verify node host keys`
- **THEN** the title becomes `fix(security): verify node host keys`, the model records no request, and the item holds one job comment that names `security`

### Requirement: Retitle shortens a corrected long title
When the corrected title has a summary over `SUMMARY_MAX_CHARS`, the retitle job SHALL shorten it in the same round. When no valid summary comes, it SHALL write the corrected type with the old summary, so that a later round selects the item for its long summary.

#### Scenario: The model shortens the corrected title
- **WHEN** the job corrects `security(zsh): <summary of 80 characters>` and the model gives a valid summary
- **THEN** the new title is `fix(security): <that summary>`, and the request of the model holds `fix(security)`

#### Scenario: The model gives no valid summary
- **WHEN** both replies of the model are over the limit
- **THEN** the new title is `fix(security): <the old summary>`, and the next selection holds the item

### Requirement: Retitle comments on a type with no correction
The retitle job SHALL leave an item whose title type is not listed and has no correction, and an item whose title a person set with an unlisted type. It SHALL write one comment that names the type and the types, and the correction when one exists, and the skip mark, so a later round adds no comment.

#### Scenario: A type with no correction
- **WHEN** the job runs twice with `--confirm` on an item titled `wip(cli): finish the half-done work`
- **THEN** the title stays, the item holds one job comment that names `wip` and each listed type, and the model records no request

#### Scenario: A person set the security title
- **WHEN** a person renamed the item to `security(ssh): verify node host keys` after the last job comment, and the job runs twice
- **THEN** the title stays, and the item holds one job comment that names `security` and `fix(security): verify node host keys`

### Requirement: Retitle logs each skip once
For each item it leaves, the retitle job SHALL write one log line that names the item and a reason key: `invalid-title-type` for an unlisted type, else `long-title`. The skip mark SHALL keep a later round from a second line while the title, the body and the plan mark stay the same.

#### Scenario: Two rounds over a type with no correction
- **WHEN** the job runs twice with `--confirm` on an item titled `wip(cli): finish the half-done work`
- **THEN** the log holds one line for the item, and the line holds `invalid-title-type`

### Requirement: Intake keeps a candidate with an unlisted title type
`devops roadmap intake --title` SHALL NOT refuse a new candidate because its title type is not in `CONST_BRANCH_TYPES`, also when its summary is over `SUMMARY_MAX_CHARS`. The retitle job corrects the type of the new item.

#### Scenario: Intake with a long security title
- **WHEN** a new candidate has the title `security(zsh): <summary of 80 characters>`
- **THEN** the title check of intake refuses nothing

### Requirement: The stage reason names the unlisted title type
For a title whose type is not in `CONST_BRANCH_TYPES`, the reason of the stage job and of the implement job SHALL name the type and `devops roadmap retitle`, with the corrected title when the type has a correction. For a title with no type, the reason SHALL NOT name the retitle job, because the job does not select that title.

#### Scenario: A security title
- **WHEN** the stage job leaves out an item titled `security(ssh): verify node host keys`
- **THEN** the report line names `security` and `fix(security): verify node host keys`

#### Scenario: A type with no correction
- **WHEN** the stage job leaves out an item titled `wip: no type`
- **THEN** the report line names `wip` and says that `devops roadmap retitle` comments on the item

#### Scenario: A title with no type
- **WHEN** the stage job leaves out an item titled `The board is slow`
- **THEN** the report line says "The title has no Conventional Commit type, so the branch has no type." and does not name the retitle job

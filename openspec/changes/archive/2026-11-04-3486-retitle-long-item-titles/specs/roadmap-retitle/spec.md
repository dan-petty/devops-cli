## Purpose
How `devops roadmap retitle` and the guards around it keep the title summary of roadmap items within the limit of 60 characters, so that the stage job and the implement job do not leave out an item for its title.

## ADDED Requirements

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
With `--confirm`, the repair pass SHALL replace only the summary, keep the type and the scope, and write a title that passes `title_problems`. It SHALL write one comment with the marker of the job.

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

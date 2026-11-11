## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Confirmed repair keeps type and scope
With `--confirm`, the repair pass SHALL replace only the summary of a title whose type is in `CONST_BRANCH_TYPES`, keep that type and the scope, and write a title that passes `title_problems`. It SHALL write one comment with the marker of the job. A title with an unlisted type gets the type of "Retitle corrects an unlisted title type".

#### Scenario: Confirmed repair
- **WHEN** the repair pass runs with `--confirm` on an item titled `fix(roadmap): ...` with a 68-character summary
- **THEN** the new title starts with `fix(roadmap): `, its summary has at most 60 characters, and `title_problems` returns no problem

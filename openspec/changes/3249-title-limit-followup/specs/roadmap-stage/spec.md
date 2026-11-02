## MODIFIED Requirements

### Requirement: A staged item gets a draft pull request
The job SHALL open a draft pull request whose title is `docs(openspec): plan #<issue> <summary>` and whose body starts with `Plans #<issue>` and holds no closing keyword. The part of the title after the colon SHALL have at most 60 characters. The job SHALL NOT cut the title: the schema accepts a summary only when the title holds it whole for an issue number of up to 6 digits, and for a longer number the job SHALL stop that item with an error. The job SHALL NOT mark the pull request ready: the row `stage_ready` of the Service does.

#### Scenario: The draft opens
- **WHEN** the job stages a Ready bug
- **THEN** a draft pull request opens with a body that starts with `Plans #<issue>`

#### Scenario: The body names no closing keyword
- **WHEN** the plan of the model holds the text `Closes #12` in its description of the change
- **THEN** the job stops that item with a failure that names the closing keyword, and pushes nothing

#### Scenario: The title of a bug and of a feature
- **WHEN** the job stages item 12, a bug, and item 13, a feature
- **THEN** the title of each draft starts with `docs(openspec): plan #12 ` and `docs(openspec): plan #13 `, and the branch of each keeps the type of its issue

#### Scenario: A summary at the limit
- **WHEN** the model gives a summary of the most characters that the schema accepts (47: the room after `plan #<issue> ` for an issue number of 6 digits) for item 7 and for item 3249
- **THEN** the title holds the whole summary, ends with no `...`, and passes the form check of titles, and the planner prompt names the same limit

#### Scenario: A long summary
- **WHEN** the model gives a summary that has more than 47 characters as the title shows it, such as 48 characters, or 47 characters with a handle that gets a code span
- **THEN** the schema refuses the reply, the reply goes back to the model with the count and the limit, and a second refusal stops that item only

#### Scenario: Spare whitespace costs nothing
- **WHEN** the model gives a summary of 47 characters followed by a new line
- **THEN** the schema accepts the reply, because the title shows the text on one line

#### Scenario: A number of 7 digits
- **WHEN** the job builds the title of item 1000000 for a summary of 47 characters
- **THEN** the job stops that item with an error that names the limit, and the title is not cut

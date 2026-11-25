## MODIFIED Requirements

### Requirement: A staged item gets a draft pull request
The job SHALL open a draft pull request whose title is `docs(spec): plan #<issue> <summary>` and whose body starts with `Plans #<issue>` and holds no closing keyword. The part of the title after the colon SHALL have at most 60 characters, and the job SHALL NOT cut it: the schema keeps a summary short enough for an issue number of up to 6 digits, and a longer number stops that item with an error. The job SHALL NOT mark the pull request ready: the row `stage_ready` of the Service does.

#### Scenario: The draft opens
- **WHEN** the job stages a Ready bug
- **THEN** a draft pull request opens with a body that starts with `Plans #<issue>`

#### Scenario: The body names no closing keyword
- **WHEN** the plan of the model holds the text `Closes #12` in its description of the change
- **THEN** the job stops that item with a failure that names the closing keyword, and pushes nothing

#### Scenario: The title of a bug and of a feature
- **WHEN** the job stages item 12, a bug, and item 13, a feature
- **THEN** the title of each draft starts with `docs(spec): plan #12 ` and `docs(spec): plan #13 `, and the branch of each keeps the type of its issue

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

#### Scenario: An emoji counts as two
- **WHEN** the model gives a summary of 24 emoji, which are 24 characters and 48 UTF-16 code units
- **THEN** the schema refuses the reply, because the check `Semantic PR title` counts 48 units

#### Scenario: A blank summary
- **WHEN** the model gives a summary of spaces and new lines only
- **THEN** the schema refuses the reply, because the title would show no summary

### Requirement: The draft pull request gets the labels of its title
After the job records an item, it SHALL add to its draft pull request the `type/*` label and the `scope/*` label that the title gives, each only when `.github/labels.yml` on the default branch declares it. A label that GitHub refuses SHALL NOT delete the branch, close the draft or unset the record. The comment of the run SHALL name each label not added and the reason. Rejected credentials SHALL stop the run.

#### Scenario: The title gives a type and a scope
- **WHEN** the job stages item 1 and the labels file declares `type/docs` and `scope/spec`
- **THEN** the draft holds `type/docs` and `scope/spec` and no other label

#### Scenario: A label is refused and the branch stays
- **WHEN** GitHub refuses `type/docs` for the draft
- **THEN** the remote branch exists, the draft is open, and the record holds `stage.branch`, `stage.pr`, `stage.sha` and `stage.text_hash`

#### Scenario: A label is refused and the comment says so
- **WHEN** GitHub refuses `type/docs` for the draft and accepts `scope/spec`
- **THEN** the comment of the run names the pull request, `type/docs` and the reason, and the draft holds `scope/spec`

#### Scenario: Rejected credentials
- **WHEN** GitHub answers the label call with HTTP 401
- **THEN** the run stops with the unauthenticated error and the comment has no label note

#### Scenario: A dry run
- **WHEN** `devops roadmap stage --dry-run` runs
- **THEN** the plan lists the read of `.github/labels.yml` and the request that adds a label to the draft, and the run makes no request

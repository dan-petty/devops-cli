# Spec Delta

## MODIFIED Requirements

### Requirement: A staged item gets a draft pull request
The job SHALL open a draft pull request whose title is `docs(openspec): plan #<issue> <summary>` and whose body starts with `Plans #<issue>` and holds no closing keyword. The part of the title after the colon SHALL have at most 60 characters. The job SHALL NOT mark the pull request ready: the row `stage_ready` of the Service does.

#### Scenario: The draft opens
- **WHEN** the job stages a Ready bug
- **THEN** a draft pull request opens with a body that starts with `Plans #<issue>`

#### Scenario: The body names no closing keyword
- **WHEN** the plan of the model holds the text `Closes #12` in its description of the change
- **THEN** the job stops that item with a failure that names the closing keyword, and pushes nothing

#### Scenario: The title of a bug and of a feature
- **WHEN** the job stages item 12, a bug, and item 13, a feature
- **THEN** the title of each draft starts with `docs(openspec): plan #12 ` and `docs(openspec): plan #13 `, and the branch of each keeps the type of its issue

#### Scenario: A long summary
- **WHEN** the model gives a summary of 60 characters for item 2656
- **THEN** the title after the colon has at most 60 characters, and the summary is cut at a word

## ADDED Requirements

### Requirement: The Service marks a green stage pull request ready
The row `stage_ready` of the status lane SHALL mark a draft pull request ready for review when the record of an open item holds it as `stage.pr` and all its check runs ended and passed. It SHALL read only the pull requests that the stage job recorded. It SHALL leave a draft with a failed, cancelled, unread or running check, or with no check, and SHALL NOT retry a check.

#### Scenario: Every check passed
- **WHEN** the record of an open item holds a draft `stage.pr` whose check runs all passed
- **THEN** the round marks the pull request ready once, and the record holds `stage.ready` with its number

#### Scenario: A check failed, a check runs, or no check exists
- **WHEN** the head of a recorded draft has a failed check, a running check, or no check run
- **THEN** the round marks no pull request ready and records nothing

#### Scenario: A draft of a person
- **WHEN** a draft pull request is open, green and recorded in no item
- **THEN** the round sends no request for it and marks it ready never

#### Scenario: The same pull request twice
- **WHEN** a second round runs after the first marked the pull request ready
- **THEN** the second round sends no request

#### Scenario: A pull request that left the draft state
- **WHEN** the recorded pull request is ready, merged or closed
- **THEN** the round records `stage.ready` and calls `gh pr ready` never

#### Scenario: No recorded draft
- **WHEN** no open item holds a `stage.pr` that `stage.ready` has not recorded
- **THEN** the round sends no request

#### Scenario: A Job works on the item
- **WHEN** the record of the item holds `implement.job`
- **THEN** the round leaves its pull request a draft

#### Scenario: One item fails
- **WHEN** `gh pr ready` fails for the first of two green drafts
- **THEN** the second pull request is marked ready, and the round fails naming the first item

#### Scenario: The check runs only
- **WHEN** a recorded draft is green
- **THEN** the round sends no request to the commit status endpoint

### Requirement: The row reads again before it marks and stops on a rate limit
The row SHALL read the pull request again before it marks, and SHALL leave a draft whose head moved. A rate limit, rejected credentials and the stop of the Service SHALL stop the round. Any other error SHALL fail its item only.

#### Scenario: A push after the read of the checks
- **WHEN** the head of a recorded draft changes between the read of its checks and the mark
- **THEN** the round marks no pull request ready and records nothing

#### Scenario: GitHub cannot find the pull request
- **WHEN** GitHub answers 404 for the read of a recorded pull request
- **THEN** the round records nothing, reads the pull request again in the next round, and fails naming the item

#### Scenario: A rate limit
- **WHEN** GitHub refuses a read for the rate limit
- **THEN** the round stops at once and sends no request for the pull requests that follow

### Requirement: One function decides, and one function marks
`ready_to_mark` SHALL be the only function that decides whether a recorded draft is marked. The row SHALL mark with `mark_ready`, the function the implement job uses, and SHALL record `stage.ready` with the number of the pull request, so that no later round reads it.

#### Scenario: The implement job and the row mark the same way
- **WHEN** the implement job and the row each mark a pull request ready
- **THEN** both run `gh pr ready <number> --repo <repo>`

#### Scenario: The decision is replaced
- **WHEN** a test replaces `ready_to_mark` with a function that returns false
- **THEN** the round marks no pull request

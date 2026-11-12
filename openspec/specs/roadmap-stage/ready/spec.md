# roadmap-stage/ready Specification

## Purpose
How the Service marks a green stage draft ready for review: the check for open findings, the read before the mark, and the Jev check of the criteria.

## Requirements

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

### Requirement: The row refuses a plan with an open finding
The row `stage_ready` SHALL NOT mark a pull request that holds the label `plan/needs-fix`. It SHALL leave that draft and comment once that the label is the reason, and it SHALL record `stage.needs_fix` with the number of the pull request.

#### Scenario: A green draft with an open finding stays in draft
- **WHEN** every check of a staged draft pull request has passed and the pull request holds the label `plan/needs-fix`
- **THEN** the row leaves the pull request in draft and posts a comment that names the label as the reason

#### Scenario: The row states the reason once
- **WHEN** two rounds read a green draft pull request that holds `plan/needs-fix`
- **THEN** the first round posts one comment that names the label and records `stage.needs_fix`, and the second round makes no second comment

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
`draft_readiness` SHALL be the only function that decides whether a recorded draft is marked. The row SHALL mark with `mark_ready`, the function the implement job uses, and SHALL record `stage.ready` with the number of the pull request, so that no later round reads it.

#### Scenario: The implement job and the row mark the same way
- **WHEN** the implement job and the row each mark a pull request ready
- **THEN** both run `gh pr ready <number> --repo <repo>`

#### Scenario: The decision is replaced
- **WHEN** a test replaces `draft_readiness` in `stage_ready` with a function that answers refuse
- **THEN** the round marks no pull request

### Requirement: An open finding keeps the plan in draft
When the last review of a plan returns a finding that has a quote in its input or in a tool answer of the run and a defect type of `missing_path`, `false_premise`, `ignores_existing_code`, `task_order`, `verify_form`, `spec_delta_wrong` or `criterion_dropped`, or a finding that reports a placeholder with a quote in its request, the stage SHALL keep the plan pull request in draft, apply the label `plan/needs-fix` to it, and put those findings at the top of the stage comment.

#### Scenario: A placeholder finding from a fake client
- **WHEN** The fake verification client returns a placeholder finding whose quote is in the input.
- **THEN** The plan pull request is a draft, it holds the label `plan/needs-fix`, and its stage comment starts with the finding text.

#### Scenario: A clean review stages as today
- **WHEN** The fake verification client returns no finding with a quote in the input and an open defect type.
- **THEN** The stage opens the plan pull request as today and applies no `plan/needs-fix` label.

#### Scenario: A later clean round clears the label
- **WHEN** A stage round verifies a plan that holds `plan/needs-fix` and returns no open finding.
- **THEN** The stage removes the label from the pull request.

#### Scenario: An open task order finding
- **WHEN** The last review returns a `task_order` finding whose quote is in the input.
- **THEN** The plan pull request is a draft and it holds the label `plan/needs-fix`.

#### Scenario: A placeholder only in a tool answer
- **WHEN** The verifier reports a placeholder whose quote is in a tool answer and not in its request.
- **THEN** The finding is not open.

#### Scenario: A quoted dropped criterion finding is open
- **WHEN** A verification reply holds a `criterion_dropped` finding whose quote is in the issue.
- **THEN** `open_findings` returns the finding.

#### Scenario: An unquoted dropped criterion finding is advice
- **WHEN** A verification reply holds a `criterion_dropped` finding whose quote is in none of the issue, the plan and the cited files.
- **THEN** `open_findings` returns no finding.

#### Scenario: A test-only group with no code
- **WHEN** A group of a plan changes only a fixture file and a test file, no group changes the code that its criterion needs, and the verification reply holds a `criterion_dropped` finding that quotes the criterion of the issue.
- **THEN** `open_findings` returns the finding and `returning` returns none.

### Requirement: A plan with an open finding is a failed attempt
An item whose plan carries an open finding SHALL NOT count as a staged plan in the round budget of the Service, and its result SHALL be recorded as a failed attempt of failure class `plan_defect`.

#### Scenario: The round counts a plan with an open finding
- **WHEN** The stage records an open finding for an item and the Service counts the round.
- **THEN** The round budget counts no staged plan for the item, and the failure record of the item has class `plan_defect`.

### Requirement: The Service asks Jev about the criteria of a green stage draft
With the setting `roadmap.stage.jev_completeness` true, the row `stage_ready` SHALL ask TypeSafe Jev, after the check runs of a draft passed and before it marks the draft ready, whether the plan delivers each acceptance criterion of the item. It SHALL send one request with a Noul question for each criterion and a Score question for the tests. Otherwise it SHALL send no request to Jev.

#### Scenario: The setting is off
- **WHEN** the setting is false
- **THEN** the round sends no request to Jev

#### Scenario: A check did not pass
- **WHEN** a check run of the draft failed or is running
- **THEN** the round sends no request to Jev

#### Scenario: Jev does not doubt
- **WHEN** every criterion has a probability at or above `CONST_ROADMAP_JEV_CRITERION_THRESHOLD` and the tests score at least `CONST_ROADMAP_JEV_MIN_TEST_SCORE`
- **THEN** the round marks the pull request ready as it does without the check, and the record holds no `stage.jev`

### Requirement: A doubt or an error of Jev only holds the draft
A criterion below the threshold, a test score below the minimum, or an error of Jev SHALL keep the pull request a draft and post one note that lists the points in doubt. The round SHALL record `stage.jev` with the head commit and the outcome. It SHALL NOT ask again for a head commit that it held on doubt, SHALL ask again for a new head commit and after an error, and SHALL post no second note for one head commit. The check SHALL NOT mark a pull request ready, merge or close.

#### Scenario: Jev doubts a criterion
- **WHEN** a green draft is read with the setting true and Jev gives a probability below the threshold for a criterion
- **THEN** the pull request stays a draft, one note names the criterion, and `stage.jev` holds the head commit with `held`
- **AND** a second round for the same head commit sends no request to Jev and posts no second note

#### Scenario: Jev gives no answer
- **WHEN** the request to Jev fails
- **THEN** the pull request stays a draft and one note says that Jev gave no answer
- **AND** the next round asks again and posts no second note for the same head commit

#### Scenario: A new head commit
- **WHEN** a person pushes a commit to a held draft
- **THEN** the next round asks Jev again for the new head commit

### Requirement: The check skips what it cannot judge and counts its outcome
A diff over `CONST_ROADMAP_JEV_MAX_DIFF_TOKENS`, an item with no criterion, and an item with more than `CONST_ROADMAP_JEV_MAX_CRITERIA` criteria SHALL skip the check with a logged reason and no request. The check SHALL count each outcome in `devops_cli_roadmap_jev_completeness_total` with the label `outcome` of four values: `passed`, `held`, `error` and `skipped`.

#### Scenario: A diff over the bound
- **WHEN** the diff holds more tokens than the bound
- **THEN** the check sends no request, logs the reason, and counts `skipped`

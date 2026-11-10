## ADDED Requirements

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

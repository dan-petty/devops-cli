## RENAMED Requirements

- FROM: `### Requirement: Row 9 reads the checks of the newest template pull request`
- TO: `### Requirement: Row 9 reads the checks of the open template pull request`

## MODIFIED Requirements

### Requirement: Row 9 reads the checks of the open template pull request
When the repository holds each rendered file and each agent file of the template, row 9 SHALL read the check runs of the head of the open template pull request, and SHALL record the names that ended `success` and the names that ended `skipped` for row 10. A merged or closed template pull request SHALL give row 10 no check name and no check to drop: row 10 then keeps each live required check and adds the checks of the baseline and of the `github/repository.yaml` of the default branch.

#### Scenario: An open template pull request of an onboarded repository
- **WHEN** the repository holds each file of the template, the live ruleset requires `K8s`, and its open template pull request reported `K8s` as `skipped` and `PR title / Semantic PR title` as `success`
- **THEN** row 9 is `present` and the change line of row 10 names `K8s` after `; dropped`

#### Scenario: A merged template pull request with a check name that no workflow reports now
- **WHEN** the repository holds each file of the template, the live ruleset requires only `PR title / Semantic PR title`, the head of its merged template pull request reported `Semantic PR title` as `success`, and `--confirm` runs
- **THEN** rows 9 and 10 are `present`, the run sends no write, and the ruleset does not require `Semantic PR title`

#### Scenario: A merged template pull request of an onboarded repository
- **WHEN** the repository holds each file of the template, the live ruleset requires `K8s`, its newest template pull request is merged with `K8s` as `skipped` and `PR title / Semantic PR title` as `success`, and `--confirm` runs
- **THEN** rows 9 and 10 are `present`, the run sends no write, and the ruleset still requires `K8s`

### Requirement: A skipped check run adds no required check
Row 10 SHALL add a required check only from a check run of the template pull request that ended with the conclusion `success`. A check run that ended `skipped` SHALL add no check. Row 10 SHALL leave a live required check out of the desired ruleset when each check run of its name ended `skipped`, and the change line of the row SHALL name it after `; dropped`.

#### Scenario: Skipped reusable-workflow job
- **WHEN** the template pull request reported `K8s` as `skipped` and `PR title / Semantic PR title` as `success`
- **THEN** the ruleset `main` requires `PR title / Semantic PR title` and no check named `K8s`

#### Scenario: Passing check
- **WHEN** the template pull request reported `Tests` as `success`
- **THEN** the ruleset `main` requires `Tests`

#### Scenario: A live required check that only a skipped check run gave
- **WHEN** the live ruleset requires `K8s` and `PR title / Semantic PR title`, and the open template pull request reported `K8s` as `skipped`
- **THEN** row 10 is `pending` with the change `ruleset main: required checks PR title / Semantic PR title; dropped K8s`

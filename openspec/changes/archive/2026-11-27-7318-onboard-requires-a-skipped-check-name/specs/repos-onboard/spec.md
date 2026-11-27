## ADDED Requirements

### Requirement: A skipped check run adds no required check
Row 10 SHALL add a required check only from a check run of the template pull request that ended with the conclusion `success`. A check run that ended `skipped` SHALL add no check. Row 10 SHALL leave a live required check out of the desired ruleset when each check run of its name ended `skipped`, and the change line of the row SHALL name it after `; dropped`.

#### Scenario: Skipped reusable-workflow job
- **WHEN** the template pull request reported `K8s` as `skipped` and `PR title / Semantic PR title` as `success`
- **THEN** the ruleset `main` requires `PR title / Semantic PR title` and no check named `K8s`

#### Scenario: Passing check
- **WHEN** the template pull request reported `Tests` as `success`
- **THEN** the ruleset `main` requires `Tests`

#### Scenario: A live required check that only a skipped check run gave
- **WHEN** the live ruleset requires `K8s` and `PR title / Semantic PR title`, and the newest template pull request reported `K8s` as `skipped`
- **THEN** row 10 is `pending` with the change `ruleset main: required checks PR title / Semantic PR title; dropped K8s`

### Requirement: A matrix leg gives way to its job name
Row 10 SHALL NOT add the name of a matrix leg as a required check when a check run of the name of its job ended with the conclusion `success`. A matrix leg is a check name of the shape `<job> (<values>)`. Row 10 SHALL leave out a live required check of that shape when a check run of the name of its job ended `success`, and the change line of the row SHALL name it after `; dropped`.

#### Scenario: Skipped matrix legs
- **WHEN** the template pull request reported `Tests & Coverage` as `success` and `Tests & Coverage (shard 1 of 5)` as `skipped`
- **THEN** the ruleset `main` requires `Tests & Coverage` and no check named `Tests & Coverage (shard 1 of 5)`

#### Scenario: Passing matrix legs
- **WHEN** the template pull request reported `Changed-Test Independence` and `Changed-Test Independence (run 1 of 3)` both as `success`
- **THEN** the ruleset `main` requires `Changed-Test Independence` and no check named `Changed-Test Independence (run 1 of 3)`

### Requirement: Row 9 reads the checks of the newest template pull request
When the repository holds each rendered file and each agent file of the template, row 9 SHALL read the check runs of the head of the newest template pull request, whatever its state, and SHALL record the names that ended `success` and the names that ended `skipped` for row 10. A repository that onboard already changed SHALL be checked again on each run.

#### Scenario: A merged template pull request of an onboarded repository
- **WHEN** the repository holds each file of the template and its newest template pull request is merged, with `K8s` as `skipped` and `PR title / Semantic PR title` as `success`
- **THEN** row 9 is `present` and the change line of row 10 names `K8s` after `; dropped`

## MODIFIED Requirements

### Requirement: The ruleset requires the reported and the declared checks
Row 10 SHALL write the ruleset `main` of the baseline with each required check of the live ruleset that no check run contradicts, each check run of the template pull request that ended `success` and is no matrix leg, and the required checks rule of the `github/repository.yaml` of the default branch. That file SHALL win for each parameter that it sets and each check that it names. It SHALL send `POST` when no ruleset has the name, and `PUT` only on a difference.

#### Scenario: The checks of the template pull request
- **WHEN** the check run `PR title / Semantic PR title` passed on the template pull request and `--confirm` runs
- **THEN** the ruleset requires that check and no other

#### Scenario: The checks of the repository file in a plan
- **WHEN** the `github/repository.yaml` of the default branch requires `K8s` and `Lint`, the live ruleset requires only `PR title / Semantic PR title`, and `--plan` runs
- **THEN** row 10 is `pending` with the change `ruleset main: required checks K8s, Lint, PR title / Semantic PR title`, and the run sends no write

#### Scenario: The checks of the repository file in a confirmed run
- **WHEN** that file requires `K8s` and `Lint` and sets the strict required status checks policy to true, the live ruleset requires `PR title / Semantic PR title`, and `--confirm` runs two times
- **THEN** the first run sends one `PUT` of the ruleset, which requires `K8s`, `Lint` and `PR title / Semantic PR title` with the strict policy, and the second run sends no write

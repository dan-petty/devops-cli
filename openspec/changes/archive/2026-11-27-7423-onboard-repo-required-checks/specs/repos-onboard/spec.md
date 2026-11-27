## RENAMED Requirements

- FROM: `### Requirement: The ruleset requires only reported checks`
- TO: `### Requirement: The ruleset requires the reported and the declared checks`

## MODIFIED Requirements

### Requirement: The ruleset requires the reported and the declared checks
Row 10 SHALL write the ruleset `main` of the baseline with each required check of the live ruleset, each check that reported on the template pull request, and the required checks rule of the ruleset `main` in the `github/repository.yaml` of the default branch of the repository. That file SHALL win for each parameter of the rule that it sets and for the entry of each check that it names. It SHALL send `POST` when no ruleset has the name, and `PUT` only on a difference.

#### Scenario: The checks of the template pull request
- **WHEN** the check run `PR title / Semantic PR title` passed on the template pull request and `--confirm` runs
- **THEN** the ruleset requires that check and no other

#### Scenario: The checks of the repository file in a plan
- **WHEN** the `github/repository.yaml` of the default branch requires `K8s` and `Lint`, the live ruleset requires only `PR title / Semantic PR title`, and `--plan` runs
- **THEN** row 10 is `pending` with the change `ruleset main: required checks K8s, Lint, PR title / Semantic PR title`, and the run sends no write

#### Scenario: The checks of the repository file in a confirmed run
- **WHEN** that file requires `K8s` and `Lint` and sets `strict_required_status_checks_policy` to true, the live ruleset requires `PR title / Semantic PR title`, and `--confirm` runs two times
- **THEN** the first run sends one `PUT` of the ruleset, which requires `K8s`, `Lint` and `PR title / Semantic PR title` with the strict policy, and the second run sends no write

## ADDED Requirements

### Requirement: Row 10 refuses a repository file that does not load
A `github/repository.yaml` of the default branch that does not load, or that the schema of the template at the ref of the baseline refuses, SHALL make row 10 `not readable` with a reason that names the file, and row 10 SHALL send no write.

#### Scenario: A repository file that is not YAML
- **WHEN** the `github/repository.yaml` of the default branch is not valid YAML and `--confirm` runs
- **THEN** row 10 is `not readable`, the reason names the file and the line, and the run sends no write

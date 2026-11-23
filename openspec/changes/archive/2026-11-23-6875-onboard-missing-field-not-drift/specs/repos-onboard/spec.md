## ADDED Requirements

### Requirement: A key that the reply does not hold is not readable
Rows 2 and 10 SHALL compare only the top-level keys of the baseline that the reply of GitHub holds, and SHALL NOT give a key that the reply does not hold as a change. A row with such a key and no other difference SHALL be `not readable`: its reason SHALL name each such key, and a person step SHALL name the permission that GitHub needs and the command `devops repos onboard <repo> --plan --only <row>`.

#### Scenario: A reply without the merge settings
- **WHEN** the reply of `GET /repos/<repo>` holds none of the 8 merge keys of the baseline, each other key matches, and `--plan` runs
- **THEN** row 2 is `not readable` with no change, the reason names each merge key, a person step names Contents write and the document "Get a repository", and the run sends no write

#### Scenario: A reply without the merge settings and with another difference
- **WHEN** the reply of `GET /repos/<repo>` holds none of the 8 merge keys of the baseline and holds `has_issues: false`, and `--plan` runs
- **THEN** row 2 is `pending` with the one change `has_issues: True`, and the reason names each merge key

#### Scenario: A reply with the merge settings of the baseline
- **WHEN** the reply of `GET /repos/<repo>` holds each key of the baseline with its value, and `--plan` runs
- **THEN** row 2 is `present`

#### Scenario: A ruleset reply without the bypass actors
- **WHEN** the reply of `GET /repos/<repo>/rulesets/<id>` holds no `bypass_actors`, each other key matches the baseline, and `--plan` runs
- **THEN** row 10 is `not readable`, the reason names `bypass_actors`, a person step names write access to the ruleset, and the run sends no write

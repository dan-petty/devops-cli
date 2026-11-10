## MODIFIED Requirements

### Requirement: A scenario that names code has a behavior test
`check_proposal` SHALL refuse a spec scenario that names a function or a file when no behavior group's `test` or `verify` names it and the scenario names no command. It SHALL judge the code spans of the `then`, and the code spans of the `when` that are no path or whose path a behavior group changes, creates or reads. It SHALL NOT judge a path of the `when` that no behavior group touches, because that path is input data.

#### Scenario: A scenario names `_loki_mode` and no task tests it
- **WHEN** A spec scenario's `then` names `_loki_mode` in a code span, and no behavior group's `test` or `verify` names `_loki_mode`.
- **THEN** `check_proposal` returns one problem that names the scenario and `_loki_mode`.

#### Scenario: A scenario that cites `helm template`
- **WHEN** A spec scenario's `then` names `_loki_mode` and `helm template` in code spans, and no behavior group's `test` names `_loki_mode`.
- **THEN** `check_proposal` returns no scenario problem.

#### Scenario: A behavior test names the function
- **WHEN** A spec scenario's `then` names `_loki_mode` in a code span, and a behavior group's `test` names `_loki_mode`.
- **THEN** `check_proposal` returns no scenario problem.

#### Scenario: A data file in the condition
- **WHEN** A spec scenario's `when` says `.github/labels.yml` declares no `scope/floor`, and no behavior group changes, creates or reads `.github/labels.yml`, and no test names it.
- **THEN** `check_proposal` returns no scenario problem.

#### Scenario: A file that a behavior group reads
- **WHEN** A spec scenario's `when` names `.github/labels.yml`, a behavior group reads it, and no behavior group's `test` or `verify` names it.
- **THEN** `check_proposal` returns one problem that names the scenario and `.github/labels.yml`.

#### Scenario: A file in the result
- **WHEN** A spec scenario's `then` names `.github/labels.yml` and no behavior group's `test` or `verify` names it.
- **THEN** `check_proposal` returns one problem that names the scenario and `.github/labels.yml`.

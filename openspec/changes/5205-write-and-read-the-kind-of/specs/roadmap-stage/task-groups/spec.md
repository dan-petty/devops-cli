## MODIFIED Requirements

### Requirement: A task group has a kind
A task group of the reply SHALL have a `kind`: `behavior`, `manifest` or `other`. A `behavior` group SHALL have a `test` and a `verify`, no `process`, and a path under `src/` in `changes`. A `manifest` group SHALL have a `test` and a `verify`, and no `process`. An `other` group SHALL have no `test`, and exactly one of `verify` and `process`. The reply that breaks a rule SHALL fail the schema, and the problem text SHALL name each rule it breaks.

#### Scenario: A test on an other group
- **WHEN** the reply holds an `other` group with a `test`
- **THEN** the reply fails the schema, and the model gets the problem text

#### Scenario: A behavior group with no test
- **WHEN** the reply holds a `behavior` group whose `test` is null
- **THEN** the reply fails the schema

#### Scenario: A behavior group that changes no source
- **WHEN** the reply holds a `behavior` group whose `changes` hold only `docs/TESTING.md`
- **THEN** the reply fails the schema

#### Scenario: An other group with no proof
- **WHEN** the reply holds an `other` group with no `verify` and no `process`
- **THEN** the reply fails the schema

## ADDED Requirements

### Requirement: A task group writes its kind
`group_text` SHALL write the kind of each group on the line under its heading, in the form `Kind: <kind>. Reads: <reads>. Changes: <changes>.`, so that the plan reader reads the kind back.

#### Scenario: A manifest group writes its kind
- **WHEN** `group_text` renders a `manifest` group
- **THEN** the line under its heading starts with `Kind: manifest. Reads: `

### Requirement: The problem of a behavior group with no source names the other kinds
The problem text of a `behavior` group that changes no path under `src/` SHALL name the kind `manifest` for a group that changes only a rule, a dashboard or a case file, and the kind `other` for a group with no test.

#### Scenario: A test-first group of a dashboard
- **WHEN** the reply holds a `behavior` group whose `changes` hold only a dashboard file and its test
- **THEN** the problem text names the kinds `manifest` and `other`

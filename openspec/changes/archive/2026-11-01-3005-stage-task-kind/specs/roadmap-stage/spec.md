## MODIFIED Requirements

### Requirement: A task group has the text of its tasks
A task group of the reply SHALL have a text in `title` with at least one character after its whitespace is stripped. It SHALL have a text in `implementation` with at least one character that is no space and no full stop. `test` and `documentation`, when set, SHALL have the same. `verify` and `process`, when set, SHALL have at least one character after their whitespace is stripped. `test`, `verify`, `process` and `documentation` MAY be null.

#### Scenario: A blank text
- **WHEN** the reply holds a group whose `documentation` is blank
- **THEN** the reply fails the schema

#### Scenario: A text of only full stops
- **WHEN** the reply holds a group whose `documentation` is `...`
- **THEN** the reply fails the schema, as a blank text does

#### Scenario: A group with no documentation
- **WHEN** the reply holds a group whose `documentation` is null
- **THEN** the reply passes the schema

## ADDED Requirements

### Requirement: A task group has a kind
A task group of the reply SHALL have a `kind`: `behavior` or `other`. A `behavior` group SHALL have a `test` and a `verify`, no `process`, and a path under `src/` in `changes`. An `other` group SHALL have no `test`, and exactly one of `verify` and `process`. The reply that breaks a rule SHALL fail the schema, and the problem text SHALL name each rule it breaks.

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

### Requirement: A task group renders the tasks of its kind
A `behavior` group SHALL render `n.1` as its failing test with the words "fails on the base", `n.2` as its implementation, and `n.3` as its documentation when `documentation` is set. An `other` group SHALL render `n.1` as its implementation with its `verify` or its `process`, and `n.2` as its documentation when `documentation` is set. An `other` group SHALL render no test and no words "fails on the base". A group with no `documentation` SHALL render no documentation task.

#### Scenario: A deletion that keeps behavior
- **WHEN** an `other` group deletes a definition and its `verify` is a `git grep` that must print nothing
- **THEN** its first task names the deletion and the `git grep`, and no task asks for a test

#### Scenario: A manual check
- **WHEN** an `other` group has a `process`
- **THEN** its first task holds the steps of the process

#### Scenario: A behavior group
- **WHEN** a `behavior` group has a `test`
- **THEN** its first task is the test and says "fails on the base"

### Requirement: The prompts and the validator name the same kinds
The stage prompt and the split prompt SHALL name each value of the kind and each field of a task group. The implement prompt SHALL tell the step to write the failing test first only when its group has a test task.

#### Scenario: A kind the prompt does not name
- **WHEN** a value of the kind is absent from the stage prompt
- **THEN** the guard test fails

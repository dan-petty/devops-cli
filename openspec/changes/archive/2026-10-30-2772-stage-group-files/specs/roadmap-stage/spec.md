# Spec Delta

## ADDED Requirements

### Requirement: A task group names its files
A task group of the reply SHALL name at least one path in `changes`. A path SHALL hold no backtick and no control character. `reads` MAY be empty. Every path of `creates` SHALL be a path of `changes`.

#### Scenario: A group with no changed file
- **WHEN** the reply holds a group with an empty `changes`
- **THEN** the reply fails the schema

#### Scenario: A path that breaks the line
- **WHEN** the reply holds a path with a new line or a backtick
- **THEN** the reply fails the schema

### Requirement: A task group has the text of its tasks
A task group of the reply SHALL have a text in `title` and `verify` with at least one character after its whitespace is stripped. It SHALL have a text in `test`, `implementation` and `documentation` with at least one character that is no space and no full stop.

#### Scenario: A blank text
- **WHEN** the reply holds a group whose `documentation` is blank
- **THEN** the reply fails the schema

#### Scenario: A text of only full stops
- **WHEN** the reply holds a group whose `documentation` is `...`
- **THEN** the reply fails the schema, as a blank text does

### Requirement: A reply that breaks the schema returns once
A reply of the proposal that fails the schema SHALL go back to the model once, with the field of each violation. A second reply that fails the schema SHALL stop the item with the class `StructuredOutputValidationError` and the count of violations.

#### Scenario: A valid second reply
- **WHEN** the first reply holds a group with an empty `changes` and the second reply is valid
- **THEN** the model gets two requests, the second names `groups[0].changes`, and the item is staged

#### Scenario: A second reply that fails
- **WHEN** both replies hold a blank `documentation`
- **THEN** the model gets two requests, and the item stops with the class `StructuredOutputValidationError`

### Requirement: A task group renders without stray punctuation
The group SHALL render as the line `Reads: <paths>. Changes: <paths>.` where an empty `reads` shows `none`, and a created path shows `(new)` after it. A rendered group SHALL hold no double full stop and no task that starts with a comma.

#### Scenario: A group with no reads
- **WHEN** a group has an empty `reads` and a `changes` that holds `src/devops_cli/sample.py`
- **THEN** its line is ``Reads: none. Changes: `src/devops_cli/sample.py`.``

#### Scenario: A created path
- **WHEN** a group has `tests/test_sample.py` in `changes` and in `creates`
- **THEN** its line shows ``Changes: `tests/test_sample.py` (new).``

#### Scenario: A task ends in a full stop
- **WHEN** the `implementation` of a group ends in a full stop or in several
- **THEN** the task renders with no full stop before the comma

## MODIFIED Requirements

### Requirement: A staged item gets one comment and a record
The job SHALL post one comment on the issue with the marker `<!-- devops roadmap stage -->` that names the branch, the pull request, the groups with their measures and the budget. The comment SHALL name each path of `changes` that is no file on the default branch and that no group creates. The job SHALL record `stage.branch`, `stage.pr`, `stage.sha` and `stage.groups` in the job record. The job SHALL NOT change the Status of the item.

#### Scenario: The comment and the record
- **WHEN** the job stages a Ready bug
- **THEN** the issue gets one comment with the marker, the record holds the four keys, and the Status is still Ready

#### Scenario: A title with no type
- **WHEN** the title of the item has no Conventional Commit type
- **THEN** the plan leaves the item out and says that its title has no type

#### Scenario: A path that exists nowhere
- **WHEN** a group changes `src/devops_cli/missing.py`, which is no file on the default branch and in no `creates`
- **THEN** the comment names `src/devops_cli/missing.py`, and the job stages the item

#### Scenario: A created path is not named
- **WHEN** a group changes `tests/test_sample.py`, which is no file on the default branch and is in `creates`
- **THEN** the comment holds no line about missing paths

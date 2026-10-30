# Spec Delta

## ADDED Requirements

### Requirement: A task group names its files and its tasks
A task group of the reply SHALL name at least one path in `changes`, and SHALL have a text in `title`, `test`, `implementation`, `documentation` and `verify` with at least one character after its whitespace is stripped. `reads` MAY be empty. Every path of `creates` SHALL be a path of `changes`. A reply that breaks a rule SHALL fail the schema, and the model SHALL get the violation through the structured-reply retry.

#### Scenario: A group with no changed file
- **WHEN** the reply holds a group with an empty `changes`
- **THEN** the reply fails the schema, the model gets a second request that names the violation, and a valid second reply stages the item

#### Scenario: A blank text
- **WHEN** the reply holds a group whose `documentation` is blank
- **THEN** the reply fails the schema, and the item stops with the class `StructuredOutputValidationError` when every retry is blank

### Requirement: A task group renders without stray punctuation
The group SHALL render as the line `Reads: <paths>. Changes: <paths>.` where an empty `reads` shows `none`, and a created path shows `(new)` after it. A rendered group SHALL hold no double full stop and no task that starts with a comma.

#### Scenario: A group with no reads
- **WHEN** a group has an empty `reads` and a `changes` that holds `src/devops_cli/sample.py`
- **THEN** its line is ``Reads: none. Changes: `src/devops_cli/sample.py`.``

#### Scenario: A created path
- **WHEN** a group has `tests/test_sample.py` in `changes` and in `creates`
- **THEN** its line shows ``Changes: `tests/test_sample.py` (new).``

#### Scenario: A task ends in a full stop
- **WHEN** the `implementation` of a group ends in a full stop
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

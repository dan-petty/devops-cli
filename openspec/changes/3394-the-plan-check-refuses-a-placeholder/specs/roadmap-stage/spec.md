## MODIFIED Requirements

### Requirement: A plan text is no placeholder
`content_problems` SHALL refuse a plan text that holds a placeholder word, or that is shorter than `PLAN_FIELD_MIN_CHARS`, and the problem SHALL name the field that holds it. The checked texts SHALL be `why`, `existing_tool`, each line of `feasibility`, each line of `what_changes`, `pull_request_body`, each decision and each task.

#### Scenario: Short why is refused
- **WHEN** A plan has a `why` shorter than `PLAN_FIELD_MIN_CHARS`.
- **THEN** `content_problems` returns a problem that names `why` and the least length.

#### Scenario: Placeholder existing tool is refused
- **WHEN** A plan has an `existing_tool` that is a placeholder word.
- **THEN** `content_problems` returns a problem that names `existing_tool` and the placeholder word.

#### Scenario: Short feasibility line is refused
- **WHEN** A plan has a `feasibility` line shorter than `PLAN_FIELD_MIN_CHARS`.
- **THEN** `content_problems` returns a problem that names `feasibility`.

#### Scenario: A short real sentence is accepted
- **WHEN** A plan has a `why` that is short and holds no placeholder word.
- **THEN** `content_problems` returns no problem for it.

#### Scenario: The placeholder rule is the rule of the pull request form
- **WHEN** A plan text is `TBD`, `x`, `None.` or `placeholder`.
- **THEN** `content_problems` returns a problem that says the text is a placeholder.

#### Scenario: A placeholder in the pull-request body
- **WHEN** A valid `StageProposal` has `pull_request_body` set to `placeholder`.
- **THEN** `content_problems` returns a problem that names `pull_request_body` and the placeholder word.

#### Scenario: A placeholder in a What Changes line
- **WHEN** A valid `StageProposal` has `what_changes` set to `["placeholder"]`.
- **THEN** `content_problems` returns a problem that names `what_changes` and the placeholder word.

#### Scenario: A pull-request body below the least length
- **WHEN** A valid `StageProposal` has a `pull_request_body` shorter than `PLAN_FIELD_MIN_CHARS`.
- **THEN** `content_problems` returns a problem that names `pull_request_body` and the least length.

#### Scenario: A What Changes line below the least length
- **WHEN** A valid `StageProposal` has a `what_changes` line shorter than `PLAN_FIELD_MIN_CHARS`.
- **THEN** `content_problems` returns a problem that names `what_changes` and the least length.

#### Scenario: A valid body and valid What Changes
- **WHEN** A `StageProposal` has a `pull_request_body` and `what_changes` lines that are long enough and hold no placeholder.
- **THEN** `content_problems` returns no problem.

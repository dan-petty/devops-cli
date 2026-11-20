## ADDED Requirements

### Requirement: A form-check failure writes its class and its parts on the result line
A refine attempt whose job failure holds a form check SHALL write `class=form_check` on its result line, and SHALL write each failed part as a name of the line, such as `failed_1=acceptance_criteria.0.then`, so such a line writes no `class=none`.

#### Scenario: The result line of a form-check failure
- **WHEN** a test runs a refine round whose first criterion has an empty `then`
- **THEN** the result line holds `class=form_check` and `failed_1=acceptance_criteria.0.then`

## ADDED Requirements

### Requirement: A plan body is built and checked in one module
`pull_form` SHALL build the body of a plan pull request with `build_plan_body`: the text, the line `Plans #<issue>`, the line `Change:` with the active change folder, in the order that `plan_body_problems` judges. The builder SHALL raise `ValidationError` with every problem when the body breaks the plan form, and SHALL NOT cut the text.

#### Scenario: A plan body in the form
- **WHEN** the builder gets a text of 100 characters, issue 42 and the folder `openspec/changes/42-x`
- **THEN** it returns a body that has the line `Plans #42` and the line ``Change: `openspec/changes/42-x/` ``, and `plan_body_problems` finds no problem

#### Scenario: A text that is a placeholder
- **WHEN** the builder gets the text `placeholder`
- **THEN** it raises `ValidationError`, and the message says that the body is a placeholder

#### Scenario: A text that closes an issue
- **WHEN** the builder gets a text that holds `Closes #7`
- **THEN** it raises `ValidationError`, and the message says that a plan closes no issue

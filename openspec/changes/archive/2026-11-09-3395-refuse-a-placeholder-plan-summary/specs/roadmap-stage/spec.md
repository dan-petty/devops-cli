## ADDED Requirements

### Requirement: A plan summary is no placeholder
The stage plan SHALL refuse a `summary` whose whole text is a placeholder word through `is_placeholder` of `src/devops_cli/roadmap/pull_form.py`. The refusal SHALL use the existing `stage_problem_text_placeholder` message with the field `summary`.

#### Scenario: A summary of one placeholder word
- **WHEN** A reply gives a `summary` of `x`.
- **THEN** The schema refuses the reply, and the problem names `summary`, the placeholder rule and the text `x`.

#### Scenario: A placeholder summary message
- **WHEN** A reply gives a `summary` of `todo`.
- **THEN** The error text is the rendered `stage_problem_text_placeholder` message for the field `summary` and the text `todo`.

#### Scenario: A real summary is accepted
- **WHEN** A reply gives a `summary` of `Refuse a placeholder plan summary`.
- **THEN** The schema returns no problem for `summary`.

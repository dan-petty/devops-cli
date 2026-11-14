## ADDED Requirements

### Requirement: The inbox lists each open owner question
`devops roadmap inbox` SHALL list each open owner question as a line of kind `owner` with the item number, the age, the question and the command that answers it.

#### Scenario: One open question
- **WHEN** One open item holds an open owner question.
- **THEN** `devops roadmap inbox` shows one line with kind `owner`, the item number, the age, the question and the command `gh issue comment <number> --body "<answer>"`.

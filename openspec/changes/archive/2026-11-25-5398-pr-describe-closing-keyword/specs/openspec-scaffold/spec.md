## ADDED Requirements

### Requirement: Scaffold Why comment has no closing keyword
`scaffold_proposal` SHALL cite the issue number in the `Why` comment without any GitHub closing keyword.

#### Scenario: Scaffold proposal text
- **WHEN** a test calls `scaffold_proposal(5345)`
- **THEN** the `Why` section cites `#5345` and does not contain `Closes #5345` or trigger `closing_keyword_in`

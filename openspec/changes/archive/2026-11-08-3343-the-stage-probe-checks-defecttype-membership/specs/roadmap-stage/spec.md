## ADDED Requirements

### Requirement: A plan that names a defect type member passes
`check_proposal` MUST NOT return a problem for a plan that names a `DefectType` member, including a member that the plan adds.

#### Scenario: A plan adds a member and names it
- **WHEN** `check_proposal` runs on a valid plan whose group changes `src/devops_cli/roadmap/stage_eval_cases.py` and whose test text names `DefectType.PROMPT_KEY_MISSING`
- **THEN** `check_proposal` returns an empty list

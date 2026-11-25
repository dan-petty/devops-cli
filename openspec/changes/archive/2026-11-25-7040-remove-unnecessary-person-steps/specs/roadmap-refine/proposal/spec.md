## ADDED Requirements

### Requirement: Refine limits person questions to owner-only acts
The refine reply prompt `src/devops_cli/ai/tasks/roadmap_refine_reply.md` SHALL limit questions of `kind` `person` to decisions the project reserves for a person (`a merge, a secret, a repository setting or a host`), and SHALL NOT list `a review verdict` or `a milestone` as person-only decisions.

#### Scenario: Refine reply prompt restricts person questions to owner-only decisions
- **WHEN** a test reads `src/devops_cli/ai/tasks/roadmap_refine_reply.md`
- **THEN** it contains `a merge, a secret, a repository setting or a host` and contains neither `a review verdict` nor `a milestone`

## MODIFIED Requirements

### Requirement: A plan pull request is judged by the rules of a plan
A pull request whose title is `docs(spec): plan #<issue> <summary>` or legacy `docs(openspec): plan #<issue> <summary>` SHALL be judged by the rules of a plan and not by the rules of a delivery, and the verdict SHALL hold no blocker that asks for a closing issue or an archived folder.

#### Scenario: A valid plan is ready
- **WHEN** the title is `docs(spec): plan #3183 add plan-check`, the body has the line `Plans #3183`, and the pull request adds `openspec/changes/3183-add-plan-check/proposal.md`
- **THEN** the verdict has no grounding blocker and sends no closing-issues request.

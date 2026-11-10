## MODIFIED Requirements

### Requirement: Project skills stay synchronized across all three agent skill roots
Every skill directory in `.agents/skills/`, `.claude/skills/`, and `.kilocode/skills/` (`ask-jev`, `devops-openspec-new`, `devops-pr-ci`, `devops-review`, `devops-roadmap`, and `new-scaffold`) SHALL exist in all three roots with identical `SKILL.md` content.

#### Scenario: The skill roots are compared
- **WHEN** the invariant test inspects `.agents/skills`, `.claude/skills`, and `.kilocode/skills`
- **THEN** all three directories contain the same six skill folders and identical `SKILL.md` files

## ADDED Requirements

### Requirement: The stage context lists the sibling trees of a created file
The stage context SHALL list every other sibling tree that holds a file whose relative path matches the glob of a file that a plan creates.

#### Scenario: Skill tree siblings
- **WHEN** A plan creates `.claude/skills/new-scaffold/SKILL.md`, and `.agents/skills/openspec-x/SKILL.md` and `.kilocode/skills/openspec-y/SKILL.md` exist.
- **THEN** The context names `.agents/skills/` and `.kilocode/skills/`, and not `.claude/skills/`.

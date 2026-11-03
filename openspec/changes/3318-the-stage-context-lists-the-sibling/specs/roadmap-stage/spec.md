## ADDED Requirements

### Requirement: The stage context lists the sibling trees of a created file
The stage context SHALL list every other sibling tree that holds a file whose relative path matches the glob of a file that a plan creates.

#### Scenario: Skill tree siblings
- **WHEN** A plan creates `.claude/skills/new-scaffold/SKILL.md`, and `.agents/skills/openspec-x/SKILL.md` and `.kilocode/skills/openspec-y/SKILL.md` exist.
- **THEN** The context names `.agents/skills/` and `.kilocode/skills/`, and not `.claude/skills/`.

### Requirement: The stage context omits a single sibling tree
The stage context SHALL omit the sibling tree list when no other tree holds a file that matches the glob.

#### Scenario: Single matching tree
- **WHEN** Only `.claude/skills/openspec-x/SKILL.md` exists, and a plan creates `.claude/skills/new-scaffold/SKILL.md`.
- **THEN** The context holds no sibling tree list.

### Requirement: The stage prompt asks for each tree or a reason
The stage prompt SHALL ask the plan to create the file in each listed sibling tree or to state in the design why one tree is enough.

#### Scenario: Prompt instruction
- **WHEN** The stage context lists one or more sibling trees.
- **THEN** The rendered prompt holds the list and that instruction.

### Requirement: A sibling tree matches the relative path
The stage context SHALL list a sibling tree only when that tree holds a file whose relative path matches the same glob.

#### Scenario: Same basename, different path
- **WHEN** `.agents/notes/SKILL.md` exists and `.agents/skills/openspec-x/SKILL.md` does not.
- **THEN** The context does not list `.agents/notes/`.

### Requirement: The sibling trees are sorted
The stage context SHALL list sibling tree names in ascending alphabetical order.

#### Scenario: Sorted output
- **WHEN** The context lists `.kilocode/skills/` and `.agents/skills/`.
- **THEN** `.agents/skills/` comes before `.kilocode/skills/`.

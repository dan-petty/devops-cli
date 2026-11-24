## ADDED Requirements

### Requirement: The refine context holds the AGENTS.md of the item's commit
The refine context SHALL hold the `AGENTS.md` of the item's `sha` under its own heading, before the `CONTEXT.md` section and the ADR sections, cut to `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` tokens.

#### Scenario: A commit with an AGENTS.md
- **WHEN** the context is built for a commit whose AGENTS.md holds a known first rule line
- **THEN** the context holds that line under the rules heading

#### Scenario: The rules section comes first
- **WHEN** the commit holds an AGENTS.md and a CONTEXT.md
- **THEN** the rules heading comes before the CONTEXT.md heading

#### Scenario: A 44,535-character AGENTS.md
- **WHEN** the AGENTS.md at the item's sha holds 44,535 characters
- **THEN** the rules section holds at most the cap and ends with the mark of a cut

### Requirement: The rules section comes from the item's commit and not the working tree
The refine context SHALL read the `AGENTS.md` at the item's `sha` and SHALL NOT read the `AGENTS.md` of the working tree.

#### Scenario: The working tree differs from the commit
- **WHEN** the AGENTS.md at the sha holds one rule line and the working-tree AGENTS.md holds another
- **THEN** the context holds the line of the sha and not the working-tree line

### Requirement: The refine context gets the generic rules when the commit holds none
The refine context SHALL hold one section of the generic kit rules, under a heading that states that they are generic, when the item's commit holds no `AGENTS.md`.

#### Scenario: A commit with no AGENTS.md
- **WHEN** the item's commit holds no AGENTS.md and the working tree holds one
- **THEN** the context holds one rules section whose heading states that the rules are generic

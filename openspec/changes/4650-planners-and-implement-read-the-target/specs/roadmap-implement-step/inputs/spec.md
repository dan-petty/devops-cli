## ADDED Requirements

### Requirement: A checkout with no AGENTS.md gets the generic rules
The rules sections of a step SHALL hold one section of the kit rules first when the checkout holds no `AGENTS.md`, rendered with the toolchain that the checkout detects, under a heading that states that the rules are generic, and the routed sections that the checkout holds SHALL follow it.

#### Scenario: A checkout with no AGENTS.md
- **WHEN** the rules sections are built for a checkout that holds no AGENTS.md and no routed document
- **THEN** the result is one section, and its heading states that the rules are generic

#### Scenario: A checkout with no AGENTS.md and a routed document
- **WHEN** the checkout holds no AGENTS.md and holds docs/TESTING.md
- **THEN** the generic section comes first and the sections of docs/TESTING.md follow it

### Requirement: The generic rules name no toolchain that the checkout lacks
The generic rules SHALL name only the toolchain and the check commands that the checkout holds a manifest or a pre-push hook for, and the section SHALL be cut to `CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS` tokens.

#### Scenario: A checkout with no Python manifest
- **WHEN** the rules sections are built for a checkout that holds no AGENTS.md and no Python manifest
- **THEN** no line of the returned section says Python

# pr-merge-readiness Specification

## ADDED Requirements

### Requirement: Stage plan title wins a collision
When `implement.pr` and `stage.pr` hold the same pull request number, `kind_of` SHALL return `DraftKind.STAGE_PLAN` if the pull request title starts with `docs(openspec): plan`.

#### Scenario: Colliding plan title
- **WHEN** `kind_of` receives an item whose `implement.pr` and `stage.pr` equal the pull request and a title that starts with `docs(openspec): plan`
- **THEN** it returns `DraftKind.STAGE_PLAN`.

### Requirement: Implement title keeps a collision as implement
When `implement.pr` and `stage.pr` hold the same pull request number, `kind_of` SHALL return `DraftKind.IMPLEMENT` if the title does not start with `docs(openspec): plan`.

#### Scenario: Colliding implement title
- **WHEN** `kind_of` receives an item whose `implement.pr` and `stage.pr` equal the pull request and a title that starts with `fix(roadmap): keep the last comment`
- **THEN** it returns `DraftKind.IMPLEMENT`.

#### Scenario: Colliding with no title
- **WHEN** `kind_of` receives an item whose `implement.pr` and `stage.pr` equal the pull request and no title is given
- **THEN** it returns `DraftKind.IMPLEMENT`.

### Requirement: Read draft preserves stage plan classification
`read_draft` SHALL classify a pull request as `DraftKind.STAGE_PLAN` when its title starts with `docs(openspec): plan` and both `implement.pr` and `stage.pr` hold its number.

#### Scenario: Read draft for a colliding plan
- **WHEN** `read_draft` runs for a pull request whose title starts with `docs(openspec): plan` and whose number both records hold
- **THEN** the returned `Draft.kind` is `DraftKind.STAGE_PLAN`.

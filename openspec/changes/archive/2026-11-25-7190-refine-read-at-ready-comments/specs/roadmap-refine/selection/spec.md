## MODIFIED Requirements

### Requirement: New trusted comment is refinable
`_refinable` and `devops roadmap refine` SHALL select an open `Ready` item again, even when `unrefined_ready=False`, when a trusted person comment follows its last refine round (`refine.read_at` when set, else the newest comment carrying `CONST_ROADMAP_REFINE_COMMENT_MARKER`).

#### Scenario: Person comments on a Ready item
- **WHEN** an open `Ready` item holds a refine record and a comment by a trusted person after `refine.read_at` (or after its last refine marker comment when `refine.read_at` is absent), and `_refinable` runs with `unrefined_ready=False`
- **THEN** `_refinable` returns the item

#### Scenario: Trusted comment posted between read_at and marker comment
- **WHEN** an open `Ready` item holds `refine.read_at` earlier than its newest refine marker comment and a trusted person comment was posted between those two times
- **THEN** `_refinable` selects the item again

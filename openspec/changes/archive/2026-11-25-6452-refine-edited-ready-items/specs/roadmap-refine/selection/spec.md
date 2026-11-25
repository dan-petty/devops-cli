## ADDED Requirements

### Requirement: Edited Ready item is refinable
`_refinable` and `devops roadmap refine` SHALL select an open `Ready` item again, even when `unrefined_ready=False`, when its `refine.body_hash` is present and differs from `body_hashes(item.body)[0]`.

#### Scenario: Person edits the body of a Ready item
- **WHEN** an open `Ready` item holds `refine.body_hash` matching the old text outside the refine section, a person writes a new outside body, and `_refinable` runs with `unrefined_ready=False` and no trusted comment
- **THEN** `_refinable` returns the item

### Requirement: New trusted comment is refinable
`_refinable` and `devops roadmap refine` SHALL select an open `Ready` item again, even when `unrefined_ready=False`, when a trusted person comment follows its last refine round (`refine.repeated_at` when set, else the newest comment carrying `CONST_ROADMAP_REFINE_COMMENT_MARKER`).

#### Scenario: Person comments on a Ready item
- **WHEN** an open `Ready` item holds a refine record and a comment by a trusted person after its last refine round, and `_refinable` runs with `unrefined_ready=False`
- **THEN** `_refinable` returns the item

### Requirement: Bot comment is not refinable
`_refinable` and `devops roadmap refine` MUST NOT select an unchanged open `Ready` item again when the only comment after its last refine round was written by a bot or an untrusted account.

#### Scenario: Bot comments on a Ready item
- **WHEN** an open `Ready` item holds a matching `refine.body_hash` and a comment after its last refine round from a bot, and `_refinable` runs with `unrefined_ready=False`
- **THEN** `_refinable` returns an empty list

### Requirement: Unchanged Ready item is not refinable
`_refinable` MUST NOT select an open `Ready` item when its text outside the refine section matches `refine.body_hash` and no trusted comment follows its last refine round.

#### Scenario: Sweep with no edit and no new comment
- **WHEN** an open `Ready` item holds a matching `refine.body_hash` and no trusted comment after its last refine round, and `_refinable` runs with `unrefined_ready=False`
- **THEN** `_refinable` returns an empty list

### Requirement: Round updates body hash or returns Ready item to New on open blocker
A refine round on a selected `Ready` item SHALL record `refine.body_hash` as `body_hashes(item.body)[0]` when it stays `Ready`, and SHALL set its Status to `New` with `refine.blocked_by` and `### Dependencies` naming any open blocker found by the round.

#### Scenario: A round keeps an edited Ready item Ready
- **WHEN** `apply_refine` runs on a `Ready` item with a plan that adds no dependency and a body edited outside the refine section
- **THEN** `refine.body_hash` equals `body_hashes(item.body)[0]` and the Status stays `Ready`

#### Scenario: New scope edit or comment names an open blocker
- **WHEN** `apply_refine` runs on an edited or commented `Ready` item with a proposal naming an open issue as a dependency
- **THEN** the item Status becomes `New`, `refine.blocked_by` names the open issue, and the refine section lists the open issue under `### Dependencies`

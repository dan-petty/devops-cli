## ADDED Requirements

### Requirement: Explain names the edited body
`devops roadmap explain` SHALL report the body edit as the reason that refine is due when an open `Ready` item was edited outside its refine section after its last refine round.

#### Scenario: Explain an edited Ready item
- **WHEN** `explain_item` and `render_explanation` run on an open `Ready` item whose text outside the refine section differs from `refine.body_hash`
- **THEN** the rendered Refine line names the edit of the body

### Requirement: Explain names the new comment
`devops roadmap explain` SHALL report the new trusted comment as the reason that refine is due when an open `Ready` item has a trusted person comment after its last refine round.

#### Scenario: Explain a Ready item with a new comment
- **WHEN** `explain_item` and `render_explanation` run on an open `Ready` item with a trusted comment after its last refine round
- **THEN** the rendered Refine line names the new comment

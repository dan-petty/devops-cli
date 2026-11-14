## ADDED Requirements

### Requirement: A struck-through acceptance criterion is not a criterion
`acceptance_criteria` SHALL omit a top-level checklist item whose text starts and ends with `~~`, whether the task marker is unchecked or checked. It SHALL keep a non-struck item, an inline `~~` span included, in its original order.

#### Scenario: An unchecked struck item
- **WHEN** the section holds `- ~~[ ] Dropped criterion~~`
- **THEN** `acceptance_criteria` returns no item

#### Scenario: A checked struck item
- **WHEN** the section holds `- ~~[x] Dropped criterion~~`
- **THEN** `acceptance_criteria` returns no item

#### Scenario: A mixed list
- **WHEN** the section holds `- ~~[ ] Dropped~~`, `- [ ] Kept one` and `- [x] Kept two`
- **THEN** `acceptance_criteria` returns `["Kept one", "Kept two"]`

#### Scenario: An inline span in an active item
- **WHEN** the section holds `- [ ] Keep ~~this~~ text`
- **THEN** `acceptance_criteria` returns `["Keep ~~this~~ text"]`

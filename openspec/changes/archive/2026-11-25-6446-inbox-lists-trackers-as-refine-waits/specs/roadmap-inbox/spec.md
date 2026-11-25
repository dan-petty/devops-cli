## ADDED Requirements

### Requirement: Trackers excluded from refine inbox lines and person causes
The inbox command SHALL exclude tracker items (`Item.is_tracker` is true) from `refine`, `split`, `alternatives`, `failed`, and `owner` lines and from `devops_cli_roadmap_inbox_items` counts for those kinds.

#### Scenario: Epic tracker with refine wait record produces no refine line or gauge count
- **WHEN** an open New item carries label `type/epic` and job record key `refine.next_step` equal to `person` or `refine.returned_body_hash` equal to `refine.body_hash`
- **THEN** `read_inbox` and `refine_wait_on_person` produce no `refine` line for it and the `refine` gauge value excludes it

#### Scenario: Sub-issue tracker with split, alternatives, failed, or owner record produces no inbox line
- **WHEN** an open item has `sub_issues > 0` or label `type/epic` and holds `refine.next_step=split`, `refine.alternatives_asked`, `refine.next_step=failed`, or an unanswered `owner_question.hash`
- **THEN** `read_inbox` produces no `split`, `alternatives`, `failed`, or `owner` line for that item

#### Scenario: Non-tracker item keeps refine, split, alternatives, failed, and owner lines
- **WHEN** an open item is not a tracker and holds one of those wait keys
- **THEN** `read_inbox` lists the matching line and counts it in `devops_cli_roadmap_inbox_items`

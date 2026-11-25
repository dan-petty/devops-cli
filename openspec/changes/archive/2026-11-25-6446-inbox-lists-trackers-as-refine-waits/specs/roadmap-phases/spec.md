## ADDED Requirements

### Requirement: Tracker items ignore refine and owner person causes
`has_person_cause` SHALL return false for refine wait keys and open owner questions when `Item.is_tracker` is true.

#### Scenario: Tracker with refine or owner wait keys has no person cause
- **WHEN** a tracker item (`type/epic` or `sub_issues > 0`) holds `refine.next_step` in `("person", "split", "failed")`, matching `refine.returned_body_hash`, `refine.alternatives_asked`, `refine.blocked_by`, or unanswered `owner_question.hash`
- **THEN** `has_person_cause(item)` returns false

#### Scenario: Non-tracker item preserves person cause detection
- **WHEN** a non-tracker item holds the same refine or owner wait keys
- **THEN** `has_person_cause(item)` returns true

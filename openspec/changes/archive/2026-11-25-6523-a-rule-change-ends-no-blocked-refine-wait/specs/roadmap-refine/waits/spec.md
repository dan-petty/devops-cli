## ADDED Requirements

### Requirement: A blocked wait that older rules set gets one new look
A round SHALL refine an unchanged item that waits on `NextStep.BLOCKED` when its `refine.rules` is older than `CONST_ROADMAP_REFINE_RULES_SINCE`, or, when the record holds no version, when refine's last comment is older. A blocked wait that the current rules set SHALL stay while a recorded blocker remains open.

#### Scenario: Record older than the current rules with an open recorded blocker
- **WHEN** an item holds `refine.next_step` `blocked` with an open recorded blocker and `refine.rules` (or, when absent, refine's last comment) older than `CONST_ROADMAP_REFINE_RULES_SINCE`
- **THEN** the next round refines the item once and records `CONST_ROADMAP_REFINE_RULES_SINCE` as `refine.rules`

#### Scenario: Record at the current rules with an open recorded blocker
- **WHEN** an item holds `refine.next_step` `blocked` with an open recorded blocker and `refine.rules` equal to `CONST_ROADMAP_REFINE_RULES_SINCE`
- **THEN** the round keeps the item waiting on `blocked` and makes no model call

#### Scenario: The body still names an open dependency under the current rule
- **WHEN** the new look runs for an item whose body still names an open issue in its Dependencies section under the current rule
- **THEN** the round keeps `refine.blocked_by` naming that open issue, updates `refine.rules` to `CONST_ROADMAP_REFINE_RULES_SINCE`, and the next round keeps it waiting

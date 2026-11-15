## ADDED Requirements

### Requirement: The refine review verifies against the code-scanning alert rule description
When an item names a code-scanning alert, the refine review SHALL supply the rule description of the alert in the verification input body, and the review SHALL refuse a proposal that contradicts the alert rule description.

#### Scenario: An item naming an alert has the alert rule description in the review input
- **WHEN** An item names a code-scanning alert number
- **THEN** The verification input body holds the alert rule description

#### Scenario: Proposal contradicts the alert rule
- **WHEN** An item names a code-scanning alert and the proposal addresses a different scanner rule
- **THEN** The review refuses the proposal with a false premise defect and keeps the item in status New

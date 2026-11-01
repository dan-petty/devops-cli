## ADDED Requirements

### Requirement: partial-failure-isolation
A round with one failing item and four good items SHALL succeed and record the failure for the failing item.

#### Scenario: one-of-five-fails
- **WHEN** the alternatives row runs with five items and one item's check raises an error
- **THEN** the round completes successfully, four items have their checks written, and the failing item's job record holds the error class and the time

### Requirement: total-failure-still-fails
A round in which every item fails SHALL fail the row and count toward the three-round suspension.

#### Scenario: all-items-fail
- **WHEN** the alternatives row runs and every item's check raises an error
- **THEN** the row fails and the failure counts toward the three-round suspension

### Requirement: retry-delay
A failed item SHALL NOT be retried before the set number of days has elapsed since its failure.

#### Scenario: retry-before-set-time
- **WHEN** a later round runs before the set number of days since the item's recorded failure
- **THEN** the item is skipped and not checked again

#### Scenario: retry-after-set-time
- **WHEN** a later round runs after the set number of days since the item's recorded failure
- **THEN** the item is checked again and the failure record is cleared

## ADDED Requirements

### Requirement: Explain names a refine failure wait
For a New item whose job record holds `refine.failed_at` younger than the wait of `refine.failed_class`, `devops roadmap explain <issue>` SHALL print that the refine job is `no`, and the reason SHALL name the time after which refine takes the item again.

#### Scenario: A held item
- **WHEN** a New item's refine round failed with a `provider` error at 12:00 UTC and the clock reads 12:10
- **THEN** the refine job is `no` and the reason names 13:00

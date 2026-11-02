## ADDED Requirements

### Requirement: A problem names the group that creates a missing path
When a later group lists a missing path in `creates`, the problem SHALL name the group that names the path and the first later group that creates it, and SHALL tell the model to move the creating group before the reading group. A path that no group creates SHALL keep the problem without a creating group.

#### Scenario: A path that only a later group creates
- **WHEN** group 1 reads `tests/test_new.py` and only group 3 lists it in `creates`
- **THEN** the problem names group 1 and group 3, and tells the model to move group 3 before group 1

#### Scenario: A path that no group creates
- **WHEN** group 1 reads `tests/test_new.py` and no group lists it in `creates`
- **THEN** the problem names group 1 and names no creating group

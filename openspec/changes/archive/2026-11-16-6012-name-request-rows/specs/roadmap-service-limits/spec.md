## ADDED Requirements

### Requirement: One lane reads the open work of a repository
After a round, only the lane that holds the row `intake` SHALL read whether the repository has open work, and that read SHALL set the idle state of the repository. No other lane SHALL send the read.

#### Scenario: One poll of every lane
- **WHEN** every lane that `service_jobs` builds runs a round for one poll of a repository with open Items
- **THEN** the open issues of the repository are read once, under the row `idle_check`, and the repository is not idle

## MODIFIED Requirements

### Requirement: A failed item waits for the retry delay
The job SHALL leave an item out of the selection until the wait of its failure class has passed since `stage.failed_at`, and SHALL take the other items in the same round. The wait SHALL be `RETRY_AFTER` of the class in `stage.failed_class`, and the job SHALL NOT store the time it waits until. A record with no class, or with a class that is no failure class, SHALL wait as `ci_infra`. `--item` SHALL take the item it names. A failure time that is no time SHALL hold the item for no time. No setting SHALL change the wait.

#### Scenario: The delay has not passed
- **WHEN** the item failed 59 minutes ago with the class `provider`
- **THEN** the job leaves the item out and takes the next item

#### Scenario: The delay has passed
- **WHEN** the item failed 1 hour ago with the class `provider`
- **THEN** the job takes the item again

#### Scenario: A refused plan waits longer
- **WHEN** the item failed 1 hour ago with the class `plan_defect`
- **THEN** the job leaves the item out, and takes it again 6 hours after the failure

#### Scenario: An item that changed does not wait
- **WHEN** the item failed with the class `head_moved`
- **THEN** the job takes the item in the next round

#### Scenario: A record with no class
- **WHEN** the job record holds `stage.failed_at` of 59 minutes ago and no `stage.failed_class`
- **THEN** the job leaves the item out, and takes it 1 hour after the failure

#### Scenario: A class that is unknown
- **WHEN** the job record holds a `stage.failed_class` that is no failure class
- **THEN** the item waits as `ci_infra` and the selection does not fail

#### Scenario: A person names the item
- **WHEN** the item failed 1 minute ago and a run names it with `--item`
- **THEN** the job takes the item

#### Scenario: A stale setting
- **WHEN** a config file still holds `roadmap.stage.retry_hours`
- **THEN** the settings load without error and the stage settings hold no such field

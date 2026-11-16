## ADDED Requirements

### Requirement: Each wait that refine sets is a success
The success set of refine (`SUCCESS_RESULTS[RoadmapJob.REFINE]`) SHALL hold each value of `NextStep` that is a wait: `ready`, `person`, `split`, `blocked`, `alternatives` and `edit`. It SHALL NOT hold `retry`, `failed` or `none`. A test SHALL fail when a value of `NextStep` other than `retry`, `failed` and `none` is not in the set.

#### Scenario: A ready proposal waits on the verdict of the alternatives row
- **WHEN** the first try of refine gives a ready proposal for a public item that has no verdict of the alternatives row
- **THEN** the line holds `result=alternatives success=true first_pass=true`

#### Scenario: A try that the job failed
- **WHEN** a refine attempt sets the next step `retry`
- **THEN** the line holds `success=false first_pass=false`

#### Scenario: A new next step
- **WHEN** `NextStep` gets a new value and the success set of refine does not hold it
- **THEN** the test of the success set fails

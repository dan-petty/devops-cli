# Spec Delta

## MODIFIED Requirements

### Requirement: Failed jobs and a stalled lane warn

`RoadmapServiceJobsFailing` SHALL fire with warning severity after 30 minutes when all jobs of a repository and lane failed in 1 hour (errors increase with zero successes), joined on `repo` and `lane`. Its summary SHALL name the repository and lane, and its description SHALL give a Loki filter. `RoadmapServiceLaneStalled` SHALL fire after 10 minutes when no job started for 2 hours while a replica is available. In a new pod, the 2 hours SHALL start when the worker starts.

#### Scenario: A lane whose new error series reaches 3
- **WHEN** `promtool test rules` evaluates an error series of one repository and lane that reaches 3 in the hour with zero successes
- **THEN** `RoadmapServiceJobsFailing` fires with that repository and lane after 30 minutes

#### Scenario: A new error series with one sample
- **WHEN** `promtool test rules` evaluates a new error series with one sample of 3 and zero successes
- **THEN** `RoadmapServiceJobsFailing` fires after 30 minutes

#### Scenario: A sparse error series from before the hour
- **WHEN** `promtool test rules` evaluates an error series with samples 5, 6 and 7 at 50, 70 and 110 minutes, at 120 minutes with zero successes
- **THEN** `RoadmapServiceJobsFailing` fires after 30 minutes

#### Scenario: No available replica
- **WHEN** no job of a lane started for over 2 hours and the deployment has no available replica
- **THEN** `RoadmapServiceLaneStalled` stays quiet

#### Scenario: A worker starts
- **WHEN** a worker of a lane starts and has started no job
- **THEN** the job start gauge of its repository and lane holds the time that the worker started

#### Scenario: A lane of a new pod that starts no job
- **WHEN** `promtool test rules` evaluates the job start of the old pod, which stops, and the job start of the new pod at the start of its worker, with an available replica
- **THEN** `RoadmapServiceLaneStalled` fires with the repository and lane once more than 2 hours and 10 minutes passed since the worker started

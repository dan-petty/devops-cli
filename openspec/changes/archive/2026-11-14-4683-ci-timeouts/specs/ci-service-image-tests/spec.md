## ADDED Requirements

### Requirement: The service image suite has a bound inside the job limit
The Service Image Tests SHALL run the suite under `timeout --kill-after=30 900`, inside the 20-minute job limit.

#### Scenario: A hung suite in the image
- **WHEN** the suite in the Service image does not stop
- **THEN** `timeout` stops the container at 900 s and the step fails with 124

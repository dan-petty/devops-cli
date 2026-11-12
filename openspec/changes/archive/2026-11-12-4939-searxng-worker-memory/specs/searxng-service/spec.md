## ADDED Requirements

### Requirement: Granian replaces a worker before the memory limit
The Deployment SHALL set `GRANIAN_WORKERS_MAX_RSS` to `512`, and its memory limit SHALL hold a worker at that value and the new worker that Granian starts in its place: a request of 256 Mi and a limit of 1 Gi.

#### Scenario: A worker that grows
- **WHEN** a test reads the container of Deployment `searxng`
- **THEN** its environment holds `GRANIAN_WORKERS_MAX_RSS` with the value `512`, and its memory request is `256Mi` and its limit `1Gi`

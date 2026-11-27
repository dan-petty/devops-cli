## ADDED Requirements

### Requirement: A volume move waits for the running syncs of the paused Applications
After the pause, and again before the delete of the copy pods, the run SHALL read the phase of the sync operation of each paused Application. While it is `Running` or `Terminating`, the run SHALL wait with `kubectl wait` until the operation has `finishedAt`, up to 600 s. A wait that ends with no `finishedAt` SHALL fail the step, before the point of no return, so the run undoes its steps.

#### Scenario: A sync that still runs after the pause
- **WHEN** the paused Applications have a sync operation in the phase `Running`
- **THEN** the run waits for each of them after the pause and again before the delete of the copy pods, and only then deletes the old claim

#### Scenario: A sync that does not end
- **WHEN** the wait for a running sync operation times out
- **THEN** the run raises `VolumeMoveError`, undoes its steps, resumes the Applications, and does not delete the old claim

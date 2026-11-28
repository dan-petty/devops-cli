## MODIFIED Requirements

### Requirement: A volume move waits for the running syncs of the paused Applications
After the pause, and again before the delete of the copy pods, the run SHALL end each sync operation of a paused Application whose phase is `Running` or `Terminating`, by a patch of `status.operationState.phase` to `Terminating`, and SHALL wait up to 600 s for the phase `Failed`. An operation that still runs after the wait SHALL fail the step before the point of no return.

#### Scenario: A sync that still runs after the pause
- **WHEN** the paused Applications have a sync operation in the phase `Running`, with or without `finishedAt`
- **THEN** the run ends each of them and waits for the phase `Failed`, after the pause and again before the delete of the copy pods, and only then deletes the old claim

#### Scenario: A sync that does not end
- **WHEN** the wait for an ended sync operation times out and its phase is still `Running`
- **THEN** the run raises `VolumeMoveError`, undoes its steps, resumes the Applications, and does not delete the old claim

#### Scenario: A sync that ends by itself during the wait
- **WHEN** the operation ends in another phase than `Failed` before the end takes effect
- **THEN** the wait times out, the phase is no longer `Running`, and the move goes on

## MODIFIED Requirements

### Requirement: A failure before the old claim is deleted undoes the move
A failure before the run sends the delete of the old claim, an interrupt included, SHALL run the undo of each change of the move, the last change first, and SHALL raise `VolumeMoveError` (error code `K8S_VOLUME_MOVE_FAILED`) that names each undo step that failed. The run SHALL add each undo before it sends the change. The undo of `<claim>-move` SHALL read its volume when it runs, set the reclaim policy of that volume to `Delete`, and then delete the claim.

#### Scenario: The two sides are different
- **WHEN** the content digest of `/dst` differs from that of `/src`
- **THEN** the run deletes the source pod, scales the workload back, deletes the destination pod and `<claim>-copy`, sets the volume of `<claim>-move` to `Delete`, deletes `<claim>-move`, and resumes the Applications in reverse order, and the old claim stays

#### Scenario: A second dropped copy
- **WHEN** the copy fails two times
- **THEN** the run undoes the move as above

#### Scenario: A class that binds before the pod and retains its volumes
- **WHEN** the class of `<claim>-move` binds it at once and has the reclaim policy `Retain`, and the create of `<claim>-dst` fails
- **THEN** the undo sets the volume of `<claim>-move` to `Delete` before it deletes `<claim>-move`, so no volume of the move stays

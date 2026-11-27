## MODIFIED Requirements

### Requirement: A volume move copies the data and compares the two sides
The run SHALL make `<claim>-move`, `<claim>-copy` and the pod `<claim>-dst` on the target node, scale the workloads to zero, start `<claim>-src` with the old claim read-only, and copy with GNU tar from pod to pod over the pod network. No exec stream SHALL carry the data. When the copy fails, it SHALL empty `/dst` and copy one more time. It SHALL compare the entries, the files, the bytes of regular files, a metadata digest and a content digest of the two sides.

#### Scenario: A dropped copy
- **WHEN** the first copy fails with `connection reset by peer`
- **THEN** the run empties `/dst`, copies one more time, and goes on

#### Scenario: The copy sends no data through an exec stream
- **WHEN** a move runs its copy
- **THEN** one bash script reads the IP address of `<claim>-dst`, starts the listener in `<claim>-dst`, runs `tar -C /src --numeric-owner --sparse -cpf -` in `<claim>-src` with its output on `/dev/tcp/<ip>/7373`, and waits for the exit code of the extract, and no `kubectl exec` of the script has `-i`

### Requirement: A volume move binds the claim to the new volume
After the two sides are equal, the run SHALL set the two volumes to `Retain`, delete the copy pods and `<claim>-copy`, save the old claim to a file, delete it, delete `<claim>-move`, reserve its volume for the claim name, and make the claim again with `spec.volumeName`. The create SHALL leave out the last-applied annotation and the annotations of the volume controllers, and the run SHALL then put the saved last-applied value back.

#### Scenario: A full move
- **WHEN** a move of `monitoring/grafana` runs and every request succeeds
- **THEN** the requests that change the cluster are, in order, the three pauses, the three creates, the scale to zero, the source pod, the copy, the two `Retain` patches, the delete of the copy pods, the delete of `<claim>-copy`, the delete of the claim, the delete of `<claim>-move`, the `claimRef` patch, the create of the claim, the annotate, the scale back and the three resumes
- **AND** the claim is made with the `volumeName` of the new volume and without the last-applied annotation, and the annotate puts back the saved value

## REMOVED Requirements

### Requirement: The copy of a volume move keeps its source open until the destination has ended
**Reason**: The copy no longer pipes two exec streams. Through the API server, the stdout of an exec stream lost data at full speed and stopped with `i/o timeout` (#7408), so the data now goes from pod to pod, and no exec stream holds a source open.
**Migration**: None. The requirement "A volume move copies the data and compares the two sides" holds the new copy.

## ADDED Requirements

### Requirement: The copy pods of a volume move reach each other through a NetworkPolicy of the move
The run SHALL make the NetworkPolicy `<claim>-copy`, which selects the pods with the labels of the copy pods and allows them ingress from and egress to those pods on TCP port 7373 only, before it makes `<claim>-dst`. It SHALL delete the policy with the copy pods, and the undo SHALL delete it. The plan SHALL refuse a `<claim>-copy` of an earlier move as a leftover.

#### Scenario: A namespace that refuses traffic by default
- **WHEN** the namespace of the claim has a NetworkPolicy that selects every pod and allows no ingress and no egress
- **THEN** the source copy pod reaches the listener of the destination copy pod on port 7373, and the copy ends

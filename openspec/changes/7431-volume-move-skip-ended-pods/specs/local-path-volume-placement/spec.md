## ADDED Requirements

### Requirement: A volume move leaves out the pods that have ended
The plan SHALL leave out a pod that mounts the claim and whose phase is `Succeeded` or `Failed`. The stop step SHALL not wait for it, and the check after the start SHALL not read it.

#### Scenario: A pod that a node shutdown ended
- **WHEN** a pod of an old ReplicaSet of the workload names the claim and has the phase `Succeeded`, next to the Running pod
- **THEN** the plan names only the Running pod, the stop step waits only for it, and the move ends

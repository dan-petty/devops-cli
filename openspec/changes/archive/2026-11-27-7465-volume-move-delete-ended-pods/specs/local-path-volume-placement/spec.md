## ADDED Requirements

### Requirement: A volume move deletes the ended pods of the claim before the old claim
Right before the delete of the old claim, the run SHALL read the pods that name the claim in their volumes and have the phase `Succeeded` or `Failed`, and SHALL delete them, so that the claim protection lets the delete of the claim end.

#### Scenario: An ended pod of an old ReplicaSet
- **WHEN** a pod of an old ReplicaSet names the claim and has the phase `Succeeded`
- **THEN** the run deletes that pod after the copy pods and before the old claim, and the move ends

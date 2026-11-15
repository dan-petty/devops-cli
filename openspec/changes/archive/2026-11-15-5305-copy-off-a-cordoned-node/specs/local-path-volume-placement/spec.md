## ADDED Requirements

### Requirement: The source copy pod tolerates a cordon
`devops k8s volume move` SHALL give the source copy pod a toleration of `node.kubernetes.io/unschedulable` with `operator: Exists` and `effect: NoSchedule`, in addition to the tolerations of the workload pod.

#### Scenario: A move off a cordoned node
- **WHEN** the source node is cordoned and its workload pod holds no toleration for the unschedulable taint
- **THEN** the source copy pod schedules on that node and the move completes

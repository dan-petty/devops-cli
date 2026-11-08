## ADDED Requirements

### Requirement: The Service container has memory for the observed growth
Container `service` of `deployment/roadmap-service` SHALL request `768Mi` of memory and limit it to `3Gi`, and SHALL keep the CPU request `100m` and the CPU limit `1`. The memory limit SHALL be at least 460 MiB plus 10 hours of growth at 150 MiB each hour, so the alert `RoadmapServiceMemoryNearLimit` fires before a kill. The comment above `resources` SHALL say that the raise is a stopgap and SHALL link #4116 and #4125.

#### Scenario: The manifest is read
- **WHEN** `k8s/devops/roadmap-service/deployment.yaml` is read
- **THEN** the resources of container `service` are a memory request of `768Mi`, a memory limit of `3Gi`, a CPU request of `100m` and a CPU limit of `1`

#### Scenario: The limit is cut
- **WHEN** the memory limit of container `service` is below 460 MiB plus 10 times 150 MiB
- **THEN** the test fails and its message names #4116

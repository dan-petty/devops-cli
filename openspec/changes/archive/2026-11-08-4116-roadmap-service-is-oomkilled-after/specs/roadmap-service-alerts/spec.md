## ADDED Requirements

### Requirement: The memory alert warns before the limit
The rule group `roadmap-service` SHALL hold the warning alert `RoadmapServiceMemoryNearLimit`. It SHALL fire after 10 minutes when the working set of container `service` of a pod `roadmap-service-.+` in namespace `devops` is above 85% of the memory limit of that container. Its description SHALL end with `(k8s/README.md, Roadmap service)`, and that section SHALL name the alert and say what to do.

#### Scenario: The working set stays above 85% of the limit
- **WHEN** `promtool test rules` evaluates a working set at 90% of the limit for 20 minutes
- **THEN** `RoadmapServiceMemoryNearLimit` fires with the pod, and it does not fire at the 12th minute, before the wait ends.

#### Scenario: Another namespace or container
- **WHEN** `promtool test rules` evaluates a working set at 99% of the limit for another container of the pod, or for a pod of another namespace
- **THEN** no alert fires for it.

## ADDED Requirements

### Requirement: The description of the memory limit names the node that runs the Job
The description of the setting `roadmap.implement.max_memory_limit` SHALL name the smallest node that can run a runner Job as the bound of the limit, and SHALL name no other node as its bound.

#### Scenario: The description names the node that runs the Jobs
- **WHEN** a test reads the description of the field from the settings model
- **THEN** it names the smallest node that can run a runner Job and not the smallest node of the cluster

### Requirement: The cluster document states both runner memory limits
The Size section of the cluster document SHALL give the code default 8Gi of `roadmap.implement.max_memory_limit` and the 16Gi that the example ConfigMap sets.

#### Scenario: The Size section states both values
- **WHEN** a test reads the Size line of the cluster document
- **THEN** it names the default 8Gi and the 16Gi of the example ConfigMap

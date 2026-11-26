## MODIFIED Requirements

### Requirement: The filer groups the alerts by rule and path
The filer SHALL group the open alerts by rule id and file path, and it SHALL put the group with the worst severity first.

#### Scenario: Two alerts of one rule in one file
- **WHEN** two open alerts hold the rule id `KSV-0017` and the path `k8s/devops/cronjob.yaml`
- **THEN** the filer gives one group, and the body of the group names both alert numbers

## REMOVED Requirements

### Requirement: The privileged GPU workload holds a dated ignore entry
**Reason**: The GPU feature discovery manifest is in the environment repository, and `.trivyignore.yaml` holds no entry for it (#7290).
**Migration**: The environment repository judges the findings of its manifests.

### Requirement: The sysfs mount of the GPU workload holds a dated ignore entry
**Reason**: The GPU feature discovery manifest is in the environment repository, and `.trivyignore.yaml` holds no entry for it (#7290).
**Migration**: The environment repository judges the findings of its manifests.

### Requirement: The default pod security context of the GPU workload holds a dated ignore entry
**Reason**: The GPU feature discovery manifest is in the environment repository, and `.trivyignore.yaml` holds no entry for it (#7290).
**Migration**: The environment repository judges the findings of its manifests.

### Requirement: The GPU feature discovery workload sets a read-only root file system
**Reason**: The GPU feature discovery manifest is in the environment repository, and `.trivyignore.yaml` holds no entry for it (#7290).
**Migration**: The environment repository judges the findings of its manifests.

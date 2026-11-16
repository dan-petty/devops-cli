## ADDED Requirements

### Requirement: The cluster template lets six model Jobs run
The ConfigMap template `k8s/devops/configmap.example.yaml` SHALL set `roadmap.model_jobs` to 6, the owner choice for all repositories together. The code default of the setting SHALL stay 2.

#### Scenario: The rendered template and the code default
- **WHEN** the settings model reads the `roadmap` section of the template, and when no value sets `roadmap.model_jobs`
- **THEN** the template gives 6, and the code default is 2

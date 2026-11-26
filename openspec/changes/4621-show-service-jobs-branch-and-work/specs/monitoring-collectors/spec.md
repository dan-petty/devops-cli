## ADDED Requirements

### Requirement: kube-state-metrics keeps the Service Job series and their keys
The kube-state-metrics values SHALL keep the families `kube_job_labels`, `kube_job_annotations`, `kube_job_status_active`, `kube_job_status_start_time` and `kube_job_status_completion_time` in the includeMetrics of the kube-state-metrics metricsTuning, SHALL allow the Job labels `roadmap.devops-cli/owner`, `roadmap.devops-cli/repo`, `roadmap.devops-cli/item` and `app.kubernetes.io/component`, and SHALL allow the Job annotations `roadmap.devops-cli/branch` and `roadmap.devops-cli/worktree`.

#### Scenario: The k8s row reads the Job families and keys that the values keep
- **WHEN** `uv run devops ci --check --only k8s` runs after the kube-state-metrics values gain the jobs entries.
- **THEN** The row passes; it fails and names the key when a panel query of a committed service dashboard reads a Job family, label or annotation that those values do not keep or allow.

## ADDED Requirements

### Requirement: The Service jobs table shows the live Jobs of the Service
The dashboard of a spec whose `jobs` field is true SHALL hold a table panel named Service jobs that shows the job name, row, repository, item, branch, worktree, state, start time and duration of each live Job, SHALL read the Job labels and annotations through `kube_job_labels` and `kube_job_annotations`, and SHALL link the item to the issue and the branch to the tree of its repository on GitHub.

#### Scenario: The builder returns the table
- **WHEN** A test calls the dashboard builder with a spec whose `jobs` field is true.
- **THEN** The dashboard holds a table panel named Service jobs with the columns job, row, repo, item, branch, worktree, state, start time and duration, reads `kube_job_labels` and `kube_job_annotations` through their label_ and annotation_ names, uses `label_app_kubernetes_io_component` for the row, and links the item to `https://github.com/<owner>/<repo>/issues/<item>` and the branch to `https://github.com/<owner>/<repo>/tree/<branch>`.

### Requirement: The Work log panel shows the lines of the selected Job
The dashboard of a spec whose `jobs` field is true SHALL hold a logs panel named Work log that queries the Loki data source with the stream of the `devops` namespace and the label filter `pod=~"$job.*"`, so the derived trace field of that data source links each line to Tempo.

#### Scenario: The builder returns the Work log query
- **WHEN** A test calls the dashboard builder with a spec whose `jobs` field is true.
- **THEN** The dashboard holds a logs panel named Work log on the `loki` data source whose query is `{namespace="devops"} | pod=~"$job.*"`.

### Requirement: The Job panels filter on the repo, item and job variables
The dashboard of a spec whose `jobs` field is true SHALL offer the variables repo, item and job; the Service jobs table SHALL filter on all three, and the Work log panel SHALL filter on job.

#### Scenario: The builder returns the variables
- **WHEN** A test calls the dashboard builder with a spec whose `jobs` field is true.
- **THEN** The dashboard holds the variables `$repo`, `$item` and `$job`, the Service jobs table query holds all three, and the Work log query holds `$job`.

### Requirement: The dashboard check refuses a Job key or family that the monitoring values do not export
The `k8s` row of `devops ci` SHALL fail and name the panel and the key when the query of a panel of a committed service dashboard reads a Job metric family, label or annotation that the kube-state-metrics keep list or allowlists of `k8s/monitoring/k8s-monitoring-values.yaml` do not export.

#### Scenario: A panel reads a Job annotation that no allowlist exports
- **WHEN** A panel query of a committed service dashboard reads the Job annotation `annotation_roadmap_devops_cli_secret` and `uv run devops ci --check --only k8s` runs.
- **THEN** The check fails and names the panel and the missing key.

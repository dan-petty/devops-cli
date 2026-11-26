## ADDED Requirements

### Requirement: The Service jobs table shows the live Jobs of the Service
The dashboard of a spec whose `jobs` field is true SHALL hold the table panel `Service jobs: branch, worktree and state`, whose description names the Service jobs table. The table SHALL show the job name, row, repository, item, branch, worktree, state, start time and duration of each live Job from the `kube_job` series of kube-state-metrics, and SHALL link the item to its issue and the branch to its tree on GitHub.

#### Scenario: The builder returns the table
- **WHEN** A test calls the dashboard builder with a spec whose `jobs` field is true.
- **THEN** The table `Service jobs: branch, worktree and state` holds the columns job from `job_name`, row from `label_app_kubernetes_io_component`, repo from `label_roadmap_devops_cli_repo`, item from `label_roadmap_devops_cli_item`, branch from `annotation_roadmap_devops_cli_branch`, worktree from `annotation_roadmap_devops_cli_worktree`, state, start time and duration, and links the item to `https://github.com/<owner>/<repo>/issues/<item>` and the branch to `https://github.com/<owner>/<repo>/tree/<branch>`.

#### Scenario: The state, the start time and the duration read the status series
- **WHEN** A test reads the queries of the table of that dashboard with `selectors` of `devops_cli.prometheus.promql`.
- **THEN** The query of the state column reads `kube_job_status_active`, `kube_job_status_succeeded` and `kube_job_status_failed`, the query of the start time column reads `kube_job_status_start_time`, and the query of the duration column reads `kube_job_status_completion_time` and `kube_job_status_start_time`.

### Requirement: The Work log panel shows the lines of the selected Job
The dashboard of a spec whose `jobs` field is true SHALL hold the logs panel `Work log: lines of the selected job`, whose description names the Work log panel. The panel SHALL query the Loki data source with the stream of the `devops` namespace and the label filter `pod=~"$job.*"`, so the derived trace field of that data source links each line to Tempo.

#### Scenario: The builder returns the Work log query
- **WHEN** A test calls the dashboard builder with a spec whose `jobs` field is true.
- **THEN** The dashboard holds the logs panel `Work log: lines of the selected job` on the `loki` data source whose query is `{namespace="devops"} | pod=~"$job.*"`.

### Requirement: The Job panels filter on the repo, item and job variables
The dashboard of a spec whose `jobs` field is true SHALL offer the variables repo, item and job; the Service jobs table SHALL filter on all three, and the Work log panel SHALL filter on job. The job column of the table SHALL link to the same dashboard with the job variable set to the Job of its row.

#### Scenario: The builder returns the variables
- **WHEN** A test calls the dashboard builder with a spec whose `jobs` field is true.
- **THEN** The dashboard holds the variables `$repo`, `$item` and `$job`, the Service jobs table query holds all three, and the Work log query holds `$job`.

#### Scenario: A selected row sets the job variable
- **WHEN** A test reads the links of the job column of the table of that dashboard.
- **THEN** One link opens the dashboard of the spec with `var-job=${__value.raw}` and `${__url_time_range}`.

### Requirement: The Job panels read only the Job keys that the Service sets
Each Prometheus query of a Job panel SHALL read only families whose name starts with `kube_job`, and only the `label_` and `annotation_` names of the keys that the Service sets on its Jobs: the labels `roadmap.devops-cli/owner`, `roadmap.devops-cli/repo`, `roadmap.devops-cli/item` and `app.kubernetes.io/component`, and the annotations `roadmap.devops-cli/branch` and `roadmap.devops-cli/worktree`.

#### Scenario: A panel reads a Job annotation that the Service does not set
- **WHEN** A test gives the rule of the dashboard test a copy of the table whose query reads the annotation name of the key `roadmap.devops-cli/secret`, which the Service does not set.
- **THEN** The rule gives one line that names the panel title and that annotation name, and it gives no line for the two Job panels that the builder returns.

## ADDED Requirements

### Requirement: OpenSpec records the path and the choice
The OpenSpec change SHALL state how each value of the ConfigMap reaches the cluster today and SHALL name the chosen option with its sources.

#### Scenario: OpenSpec validator
- **WHEN** The validator `uv run devops ci --check --only openspec` runs on the change.
- **THEN** It passes with a `## Feasibility` section that names the render, the apply path, the deferred audit log and the option's sources.

### Requirement: Change record names settings
The comparer SHALL name each changed setting by its dotted path and SHALL NOT hold its value.

#### Scenario: One changed setting
- **WHEN** A test gives the comparer two rendered data maps whose `devops-cli.yaml` differs only at `ai.model`.
- **THEN** The record lists `ai.model` and holds no value of `ai.model`.

### Requirement: Annotations on the ConfigMap
`deploy-stack` SHALL put `roadmap.devops-cli/config-template-commit`, `roadmap.devops-cli/data-sha256`, `roadmap.devops-cli/changed-settings`, `roadmap.devops-cli/changed-at` and, when given, `roadmap.devops-cli/change-reason` in the manifest that it applies when the rendered data differs from the live data.

#### Scenario: Rendered annotations with a reason
- **WHEN** A test renders the manifest that `deploy-stack` applies for changed data with an issue number as the reason.
- **THEN** The rendered object holds all five annotations, and `roadmap.devops-cli/changed-settings` names the changed setting and no value.

### Requirement: History object is created when absent
`deploy-stack` SHALL create ConfigMap `devops-cli-config-changes` in namespace `devops` when the read finds none, before it adds a record key.

#### Scenario: No history object
- **WHEN** A test runs the history write against a kubectl stub that answers NotFound to the read.
- **THEN** The command applies the empty history object before it patches the record key.

### Requirement: History object holds one key for each change
`deploy-stack` SHALL add one data key `<epoch seconds>-<first 8 characters of the data SHA-256>` with one JSON line and SHALL delete each key older than 30 days in the same merge patch of ConfigMap `devops-cli-config-changes`.

#### Scenario: Add a key and prune
- **WHEN** A test builds the merge patch for one record against a history data map that holds a key older than 30 days.
- **THEN** The patch adds the new key and deletes the old key, and the new key holds only letters, digits, `-`, `_` and `.`.

### Requirement: No record when the data does not change
`deploy-stack` SHALL write no annotation, no history key and no log record when the rendered data has the same SHA-256 as the live data.

#### Scenario: An unchanged deploy
- **WHEN** A test gives the comparison the same data twice and runs the apply path.
- **THEN** It builds no record, and the command sends no history patch and logs no `configmap_changed` record.

### Requirement: No record for a failed apply
`deploy-stack` SHALL patch the history object and emit the log record only after `kubectl apply` exits 0.

#### Scenario: Failed apply
- **WHEN** A test runs the apply path with a kubectl stub that exits non-zero for the apply.
- **THEN** The command sends no patch and the log holds no `configmap_changed` record.

### Requirement: WARNING log record
`deploy-stack` SHALL emit one `configmap_changed` record at WARNING on logger `devops_cli.k8s.configmap` for each successful apply that changes the data.

#### Scenario: One record through the OTel bridge
- **WHEN** A test attaches `OTelLoggingHandler` with a fake exporter and runs the apply path with one changed setting.
- **THEN** The exporter receives one record named `configmap_changed` with the changed setting names, the template commit and the time.

### Requirement: Private values stay out
The annotations, the history line and the log record SHALL NOT hold a value of `config.yaml` or of the rendered data.

#### Scenario: Private value sentinel
- **WHEN** A test renders the record with a sentinel value under `service.repos` and a change of another setting.
- **THEN** The three records name `service.repos` and hold no sentinel value.

### Requirement: Seven-day history query
The history object SHALL answer one query that lists the changes of the last 7 days with the setting names, from lines whose `time` is an ISO-8601 UTC string.

#### Scenario: Live query
- **WHEN** The live check runs `kubectl -n devops get configmap devops-cli-config-changes -o json | jq -r '.data[] | fromjson | select((.time | fromdateiso8601) >= (now - 604800)) | [.time, (.changed_settings | join(","))] | @tsv'`.
- **THEN** It prints one line per apply of the last 7 days, each with the time and the changed setting names and no value.

### Requirement: Docs describe the record
`k8s/README.md` SHALL describe the annotation keys, the history object, the `configmap_changed` record and the seven-day query, and the Go-live check of `docs/CLUSTER.md` SHALL keep its commands.

#### Scenario: Docs validator
- **WHEN** The validator `uv run devops ci --check --only docs` runs.
- **THEN** It passes with the new `k8s/README.md` section and the unchanged Go-live check commands of `docs/CLUSTER.md`.

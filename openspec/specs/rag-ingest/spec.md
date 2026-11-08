# rag-ingest Specification

## Purpose
Ingestion of managed repositories from `service.repos` into the Qdrant vector database, scoped filtering of private repositories, and the `devops ai rag ingest` command.

## Requirements

### Requirement: Default pass over service.repos
The command `devops ai rag ingest` SHALL run one ingestion pass over `service.repos` in configured order, one repository at a time.

#### Scenario: Two configured repositories
- **WHEN** `service.repos` lists repository A then repository B and a person runs `devops ai rag ingest` with no `--repo`
- **THEN** The pass indexes A before it starts B and exits 0

### Requirement: Repository selection
The `--repo <owner>/<name>` option SHALL run only the named repositories and MUST reject a value that is not in `service.repos` with a `ConfigurationError` before any request.

#### Scenario: Unknown repository
- **WHEN** A person runs `devops ai rag ingest --repo foo/bar` and `foo/bar` is not in `service.repos`
- **THEN** The command raises `ConfigurationError` naming `foo/bar` and makes no network request

### Requirement: Empty repository list
An empty `service.repos` SHALL fail with a `ConfigurationError` naming `service.repos` before any request or removed-repository cleanup.

#### Scenario: Empty service.repos
- **WHEN** `service.repos` is empty and a person runs `devops ai rag ingest`
- **THEN** The command raises `ConfigurationError` naming `service.repos` and deletes no point

### Requirement: Visibility read and payload updates
The visibility read SHALL use `run_gh`, public SHALL count as public, and any other value SHALL count as private. If the visibility differs from the recorded value, the run SHALL rewrite `visibility` on existing points via `set_payload`.

#### Scenario: Visibility request and update
- **WHEN** A repository recorded public is read as private
- **THEN** The run updates the existing points with `visibility: private` via `set_payload`

### Requirement: Removed repository cleanup
The pass SHALL delete the points and state of a repository that the pass recorded and that `service.repos` no longer lists, and MUST touch no other project.

#### Scenario: Removed repository beside a workstation project
- **WHEN** A pass recorded `owner/name`, `owner/name` is removed from `service.repos`, and a workstation project exists in the same collections
- **THEN** The next pass deletes the points and state of `owner/name` through `delete_points_by_project` and keeps every point of the workstation project

### Requirement: Data paths containment
The checkout, cache and `state.json` SHALL sit under `repos/<owner>/<name>` in `data.rag_dir` and MUST be resolved with `safe_resolve_subpath`.

#### Scenario: Path containment
- **WHEN** The pass writes the checkout, cache and state for `owner/name`
- **THEN** Each path is under `data.rag_dir/repos/owner/name`, no file appears under `/roadmap/`, and a traversal path is refused

### Requirement: Atomic state write
The pass SHALL write `state.json` atomically with `write_json_file(..., atomic=True)` and MUST record the head only after the indexer returns.

#### Scenario: Failed run records no state
- **WHEN** The indexer raises an error after embedding part of a repository
- **THEN** No `state.json` records the new head and the next run embeds the files that were not stored

### Requirement: Qdrant URL required
The command SHALL fail with a `ConfigurationError` naming `qdrant.url` before any request or clone when `qdrant.url` is unset, and MUST NOT use the localhost default.

#### Scenario: Unset Qdrant URL
- **WHEN** Neither the configuration file nor the environment sets `qdrant.url` and a person runs `devops ai rag ingest`
- **THEN** The command raises `ConfigurationError` naming `qdrant.url` and makes no clone or network request

### Requirement: Failed repository isolation
A failed repository SHALL log one ERROR record naming the repository, the head and the error, with a traceback except for `ConfigurationError`, and the pass MUST continue with the next repository and exit 1 naming every failure.

#### Scenario: One repository fails
- **WHEN** The first of two configured repositories fails and the second is valid
- **THEN** One ERROR names the first repository with a traceback, the second repository is indexed, and the command exits 1 naming the first repository

### Requirement: Run span and metric
Each repository's run SHALL be one `trace_span` and MUST count `devops_cli_rag_ingest_runs_total{repo,result}` in `GLOBAL_METRICS`.

#### Scenario: Metric labels
- **WHEN** A pass indexes one repository successfully and fails another
- **THEN** Two spans exist and `devops_cli_rag_ingest_runs_total` has `repo` and `result` labels with `success` and `error`

### Requirement: Head check with ls-remote
The pass SHALL read the default branch and head with `git ls-remote --symref <remote> HEAD` and MUST skip embedding when the head equals the recorded commit and `points_intact` finds the project's points.

#### Scenario: Second run at the same head
- **WHEN** A second pass runs at the head recorded in `state.json` and `points_intact` returns true
- **THEN** The pass makes the visibility read, the `ls-remote` and two `count` requests, and embeds nothing

### Requirement: Shallow single-branch checkout
The pass SHALL keep a shallow, single-branch checkout at `repos/<owner>/<name>/tree` and MUST use `git clone --depth 1 --single-branch --no-tags` on the first run and `git fetch --depth 1 origin <branch>` then `git checkout --detach FETCH_HEAD` later.

#### Scenario: First and later checkout
- **WHEN** A repository has no checkout, and then its default branch moves
- **THEN** The first run makes a depth-1 single-branch clone and the later run fetches depth 1 and checks out `FETCH_HEAD` detached

### Requirement: Unscoped search filter on private visibility
A search without a project SHALL add a `must_not` condition on `visibility = private`, and a search with a project MUST search that project whatever its visibility.

#### Scenario: Private and public projects
- **WHEN** One private and one public project are indexed and a search runs without a project, then with `--project` on the private project
- **THEN** The unscoped search returns no private chunk, the scoped search returns the private chunk, and a workstation project without `visibility` still appears unscoped

### Requirement: Qdrant Secret scoped to the ingest pods
The stack SHALL reference the Qdrant credential Secret from the ingest WorkflowTemplate only.

#### Scenario: Secret references of the stack
- **WHEN** The offline manifest test renders k8s/devops and reads the secret references of every workload.
- **THEN** The test asserts that only the ingest WorkflowTemplate names the Qdrant Secret.

### Requirement: Network policy selects only the ingest pods
The stack MUST select only the ingest pods for traffic to Qdrant on port 6333, on egress from the ingest pods and on ingress to Qdrant.

#### Scenario: Pod selectors of the Qdrant rules
- **WHEN** The offline manifest test reads the Qdrant egress and ingress rules and the pod labels of the stack.
- **THEN** The test asserts that both rules select the ingest pods only and name TCP port 6333.

### Requirement: One ingest run at a time
The ingest WorkflowTemplate MUST hold the global `rag-ingest` mutex, and the CronWorkflow MUST set `concurrencyPolicy: Forbid`.

#### Scenario: Overlap is impossible
- **WHEN** The offline manifest test reads the WorkflowTemplate and the CronWorkflow.
- **THEN** The test asserts that `spec.synchronization.mutex.name` is `rag-ingest` and `spec.concurrencyPolicy` is `Forbid`.

### Requirement: Schedule follows the poll interval
The CronWorkflow MUST use the shortest whole-minute cron period that is not shorter than `service.poll_interval_seconds`.

#### Scenario: Default poll interval
- **WHEN** `service.poll_interval_seconds` holds its default of 151 seconds.
- **THEN** The test asserts that the rendered schedule is `*/3 * * * *`.

### Requirement: One embedding request at a time
The ingest template MUST set `ai.gateway_concurrency.embedding` to 1.

#### Scenario: Embedding concurrency of the template
- **WHEN** The offline manifest test reads the environment of the ingest template.
- **THEN** The test asserts that the template sets the embedding concurrency to 1.

### Requirement: Lag alert
The stack MUST ship a `RagIngestBehind` alert on the ingest freshness metric.

#### Scenario: Alert rule present
- **WHEN** The offline manifest test reads the alert rules of the stack.
- **THEN** The test asserts that one rule named `RagIngestBehind` reads the freshness metric and fires after two schedule periods without a success.

### Requirement: Stack command renders the resources
`devops k8s deploy-stack --stack all` MUST render the ingest WorkflowTemplate and the CronWorkflow.

#### Scenario: Rendered stack
- **WHEN** The offline test renders the stack with `--dry-run`.
- **THEN** The rendered output holds the WorkflowTemplate and the CronWorkflow in namespace `devops`.

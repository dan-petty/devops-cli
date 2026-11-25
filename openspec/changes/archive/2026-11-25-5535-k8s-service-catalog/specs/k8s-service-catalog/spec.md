## ADDED Requirements

### Requirement: Shared Application renderer
The catalog command SHALL render each Argo CD Application of the environment tree with the shared `application_renders` renderer.

#### Scenario: Fixture environment tree
- **WHEN** the test runs `devops k8s catalog --k8s-dir <fixture>` with one kustomize Application and one chart Application whose `helm template` output is recorded
- **THEN** the command exits 0 and writes `<fixture>/CATALOG.md` with the Services, SLOs, Workloads by Application, Stores and Cluster classes sections

### Requirement: Workload glob patterns
The catalog command SHALL match each `workloads` value as an exact workload name or an `fnmatch` pattern.

#### Scenario: Glob pattern
- **WHEN** the fixture entry has `workloads = ["ollama-*"]` and the render holds `ollama-48gib` and `ollama-64gib`
- **THEN** both workloads belong to the entry and the command exits 0

### Requirement: Operator objects are workloads
The catalog command SHALL count a CloudNativePG `Cluster` and a Mattermost resource as workloads of their catalog entry.

#### Scenario: Operator object
- **WHEN** the fixture render holds a CloudNativePG `Cluster` named `llm-gateway-db` and a Mattermost resource named `mattermost`, and entries claim them
- **THEN** the command exits 0 and the two objects appear under their entries, not as unclaimed workloads

### Requirement: UI object matched by backend Service
The catalog command SHALL assign a UI object to a service by the namespace and the workloads that its backend Service selects.

#### Scenario: UI in ingress Application
- **WHEN** the fixture render holds an Ingress in Application `ingress` whose backend Service selects workload `roadmap-service` in namespace `devops`
- **THEN** the catalog shows the `gethomepage.dev/description` annotation text on the `roadmap-service` row

### Requirement: Multiple UI descriptions
The catalog command SHALL show one description line for each UI annotation of a service, sorted by namespace and name.

#### Scenario: Two UI annotations
- **WHEN** the fixture entry has two UI objects with different annotations
- **THEN** the row shows both texts on separate lines in a stable order

### Requirement: Description sources
The catalog command SHALL take each service description from its UI annotation, else from its `description` in `k8s/catalog.toml`, else show `none`.

#### Scenario: Three description sources
- **WHEN** the fixture has one service with an annotation, one service with a catalog `description` and no UI, and one service with neither
- **THEN** the three rows show the annotation text, the catalog text and `none`

### Requirement: Duplicate description
The catalog command SHALL exit 1 when a catalog entry has a `description` and a UI object of the same service carries the annotation.

#### Scenario: Description in two places
- **WHEN** the fixture `roadmap-service` entry has `description` and its Ingress carries `gethomepage.dev/description`
- **THEN** the command exits 1 and names `roadmap-service`

### Requirement: Unclaimed workload
The catalog command SHALL exit 1 when a rendered workload belongs to no catalog entry.

#### Scenario: No entry
- **WHEN** the fixture render holds workload `open-webui` and no entry claims it
- **THEN** the command exits 1 and names `open-webui`

### Requirement: Missing object
The catalog command SHALL exit 1 when an entry names an Application or a workload that the render does not hold.

#### Scenario: Missing workload
- **WHEN** a fixture entry names workload `gone` and no render holds it
- **THEN** the command exits 1 and names `gone`

### Requirement: Unknown SLO or dashboard name
The catalog command SHALL exit 1 when a Sloth spec or a dashboard table names an unknown service or workload.

#### Scenario: Unknown Sloth service
- **WHEN** a fixture Sloth spec under `devops/monitoring/slos/` has `service = "unknown"` and the catalog holds no `unknown`
- **THEN** the command exits 1 and names `unknown`

### Requirement: Missing SLO or dashboard is not an error
The catalog command SHALL show `none` for a tier 1 or a tier 2 service with no SLO or no dashboard.

#### Scenario: Tier 1 with no SLO
- **WHEN** a fixture tier 1 service has no Sloth spec and no service dashboard table
- **THEN** the command exits 0 and the row shows `none` for the SLO and the dashboard

### Requirement: Check drift
The catalog command SHALL exit 1 when `--check` finds a difference, and exit 0 when the file matches.

#### Scenario: Out-of-date file
- **WHEN** the test runs `devops k8s catalog --check --k8s-dir <fixture>` on an out-of-date file and then on the current file
- **THEN** the first run exits 1 and the second run exits 0

### Requirement: Dry run
The catalog command SHALL make zero requests and run no `helm` with `--dry-run`.

#### Scenario: Dry run
- **WHEN** the test runs `devops k8s catalog --dry-run --k8s-dir <fixture>` with a fake client and a fake subprocess
- **THEN** no request and no subprocess call is recorded, and the command lists each chart that a run pulls

### Requirement: Sloth SLO join
The catalog command SHALL join each Sloth spec under `devops/monitoring/slos/` by its `service` field to the catalog entry with the same `name`.

#### Scenario: SLO join
- **WHEN** the fixture holds a Sloth spec under `devops/monitoring/slos/` with `service = "roadmap-service"`
- **THEN** the `roadmap-service` row shows the SLI, the objective and the window of that spec

### Requirement: Service dashboard join
The catalog command SHALL join each service dashboard from `monitoring/dashboards/services.toml` by namespace and workload.

#### Scenario: Dashboard join
- **WHEN** the fixture holds a service dashboard table for namespace `devops` and workload `roadmap-service`
- **THEN** the `roadmap-service` row shows that dashboard

### Requirement: Generated header
The catalog command SHALL write the generated line under the title of the markdown file.

#### Scenario: Generated header
- **WHEN** the test runs the command on a fixture
- **THEN** the first line under the title is "Generated by `uv run devops k8s catalog`. Do not edit this file."

### Requirement: JSON format
The catalog command SHALL write JSON with `--format json`.

#### Scenario: JSON format
- **WHEN** the test runs `devops k8s catalog --format json --k8s-dir <fixture>`
- **THEN** the command exits 0 and writes a JSON object with the services, SLOs, workloads, stores and cluster classes

### Requirement: CLI reference regenerated
`docs/CLI_REFERENCE.md` and the command page SHALL list `devops k8s catalog`.

#### Scenario: Docs generation
- **WHEN** `uv run devops docs generate` runs and then `uv run devops ci --check --only docs` runs
- **THEN** the docs check passes and the command page lists `devops k8s catalog`

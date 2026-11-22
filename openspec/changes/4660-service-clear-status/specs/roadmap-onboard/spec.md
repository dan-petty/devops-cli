## MODIFIED Requirements

### Requirement: One row for each prerequisite
`devops roadmap onboard` SHALL check six prerequisites in the documented order and SHALL print one row for each, with its number, its state and any reason or step. Row 5 SHALL be the `service.repos` row and row 6 the webhook row. The command and its dry run SHALL read no workflow file.

#### Scenario: A repository that holds every prerequisite
- **WHEN** the repository has issues turned on, the App installed, a valid labels file, every workflow label, its place in `service.repos`, and one active webhook with the Service URL, the `json` content type and the roadmap events, and it holds no `.github/workflows/clear-status.yml`
- **THEN** the six rows are `present`, row 5 is `The repository is in service.repos`, row 6 is the webhook row, and the command exits 0

#### Scenario: The dry run lists no workflow file
- **WHEN** the command runs with `--dry-run`
- **THEN** the output lists no read of `.github/workflows/clear-status.yml`

### Requirement: The exit code follows the missing rows
The command SHALL exit 1 when one of the six prerequisite rows is `missing`, and 0 when every one of them is `present` or `not readable`; a row of the index, of the visibility or of the schedule SHALL NOT change the exit code.

#### Scenario: One missing row
- **WHEN** exactly one row is `missing`
- **THEN** the command exits 1; with no `missing` row it exits 0 even when a row is `not readable`

#### Scenario: A repository that is not yet indexed
- **WHEN** Every prerequisite row is present or not readable and the indexed row reads missing
- **THEN** The command exits 0.

### Requirement: The service.repos row is printed
Row 5 SHALL print the `service.repos` line and the `devops k8s deploy-stack` step when the repository is absent from the setting, and the command MUST NOT write `config.yaml`.

#### Scenario: A repository outside service.repos
- **WHEN** the repository is not an entry of `service.repos`
- **THEN** row 5 is `missing`, the output holds the line to add and `devops k8s deploy-stack`, and `config.yaml` is unchanged

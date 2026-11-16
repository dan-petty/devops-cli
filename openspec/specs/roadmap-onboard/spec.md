# roadmap-onboard Specification

## Purpose
How `devops roadmap onboard` checks a repository for the prerequisites of the roadmap jobs and creates the missing labels.

## Requirements

### Requirement: One row for each prerequisite
`devops roadmap onboard` SHALL check seven prerequisites in the documented order and SHALL print one row for each, with its number, its state and any reason or step.

#### Scenario: A repository that holds every prerequisite
- **WHEN** the repository has issues turned on, the App installed, a valid labels file, every workflow label, the clear-status workflow, its place in `service.repos`, and one active webhook with the Service URL, the `json` content type and the roadmap events
- **THEN** every row is `present` and the command exits 0

### Requirement: The issues setting is printed, never written
When `has_issues` is false, the command SHALL set row 1 to `missing` and SHALL print the `devops gh api -X PATCH` command, and it MUST NOT send a `PATCH`.

#### Scenario: Issues are turned off
- **WHEN** the repository reports `has_issues: false`
- **THEN** row 1 is `missing`, the output holds the step `devops gh api -X PATCH repos/<owner>/<name> -f has_issues=true`, and no request of the run uses `PATCH`

### Requirement: The App row without the App key
Without the App private key in the environment, the command SHALL set row 2 to `not readable as <login>` and MUST NOT send a request to `/installation/repositories`.

#### Scenario: A run as a person
- **WHEN** `DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY` is absent from the environment
- **THEN** row 2 reads `not readable as <login>` and the fake records no request to `/installation/repositories`

### Requirement: The App row as the App
With the App private key in the environment, the command SHALL set row 2 to `present` when `GET /installation/repositories` lists the repository, and to `missing` when it does not.

#### Scenario: The installation lists the repository
- **WHEN** the environment holds the App key and the installation listing holds the repository
- **THEN** row 2 is `present`; with the repository removed from the listing, row 2 is `missing`

### Requirement: The labels file is judged
The command SHALL set row 3 to `missing` with the reason when `.github/labels.yml` is absent, is not YAML, or is not a list of labels. Row 4 SHALL then check the workflow labels of the package.

#### Scenario: Each invalid labels file
- **WHEN** each of the three invalid files is on the default branch in turn, and GitHub holds every workflow label
- **THEN** row 3 is `missing` with the matching reason and row 4 is `present`

### Requirement: Labels are created and never edited
`--confirm` SHALL send one `POST` to `repos/<owner>/<name>/labels` for each declared label that GitHub lacks, and it MUST NOT send a `PATCH` or a `DELETE` for any label.

#### Scenario: Two labels are absent and one differs
- **WHEN** `--confirm` runs on a repository that lacks two declared labels and holds a third with another color
- **THEN** the fake records two label `POST` requests, no `PATCH` and no `DELETE`, and the output lists the differing label as kept

### Requirement: A second confirm writes nothing
A second `--confirm` after a successful one SHALL send no write.

#### Scenario: Two confirms in a row
- **WHEN** `--confirm` runs twice with no change to the repository between the runs
- **THEN** the second run sends no `POST`, `PATCH` or `DELETE`

### Requirement: A dry run makes no request
`--dry-run` SHALL make no request and SHALL print the read endpoints and the possible writes with placeholders.

#### Scenario: The request plan
- **WHEN** the command runs with `--dry-run`
- **THEN** the fake records zero requests and the output lists each read endpoint and each possible write with a placeholder

### Requirement: One mode flag at a time
The command SHALL refuse two mode flags with the usage error that the other roadmap commands use, and `--plan` SHALL send no write.

#### Scenario: Two mode flags
- **WHEN** the command runs with `--plan` and `--confirm` together
- **THEN** it prints the usage error, exits 1, and sends no request

### Requirement: The exit code follows the missing rows
The command SHALL exit 1 when a row is `missing`, and 0 when every row is `present` or `not readable`.

#### Scenario: One missing row
- **WHEN** exactly one row is `missing`
- **THEN** the command exits 1; with no `missing` row it exits 0 even when a row is `not readable`

### Requirement: The service.repos row is printed
Row 6 SHALL print the `service.repos` line and the `devops k8s deploy-stack` step when the repository is absent from the setting, and the command MUST NOT write `config.yaml`.

#### Scenario: A repository outside service.repos
- **WHEN** the repository is not an entry of `service.repos`
- **THEN** row 6 is `missing`, the output holds the line to add and `devops k8s deploy-stack`, and `config.yaml` is unchanged

### Requirement: One copy of the type rule
The `type/*` rule SHALL live in one function in `src/devops_cli/roadmap/title_labels.py`, and intake and onboard SHALL both call it.

#### Scenario: The shared rule
- **WHEN** intake and onboard each read the same declared label names
- **THEN** both get the same `type/*` names other than `type/epic` from the one function

### Requirement: The command is documented
`docs/roadmap/onboard.md` SHALL document the command, and the README command list SHALL link it.

#### Scenario: The documentation invariant
- **WHEN** the documentation invariant tests run
- **THEN** they pass, `docs/roadmap/onboard.md` exists, and the README lists `devops roadmap onboard`

### Requirement: Row 4 compares GitHub with the workflow labels and the file
Row 4 SHALL compare the labels of the repository on GitHub with the workflow labels of the package and the labels of `.github/labels.yml`. With no usable file, it SHALL compare the workflow labels only. When a label is absent, row 4 SHALL be `missing`, and the output SHALL list each absent label.

#### Scenario: A repository with no status/planned
- **WHEN** GitHub holds every workflow label but `status/planned`, and every label of the file
- **THEN** row 4 is `missing` with the reason `1 label(s) missing`, the output lists `status/planned`, and the command exits 1

### Requirement: The webhook row reads the repository hooks
The `webhook` row SHALL read `GET repos/<owner>/<name>/hooks` once and SHALL print a state.

#### Scenario: The row reads hooks
- **WHEN** the installation token can read hooks
- **THEN** the row sends one GET request to `repos/<owner>/<name>/hooks`

### Requirement: A matching hook is present
The row SHALL report `present` when one active hook has `service.webhook_url`, the content type `json`, and events that hold each event of `CONST_ROADMAP_WEBHOOK_EVENTS`. The hook MAY send other events too.

#### Scenario: One active hook matches
- **WHEN** one active hook has the configured URL, `config.content_type` `json`, and the roadmap events
- **THEN** the row is `present` and names no field

#### Scenario: The hook sends more events than the Service takes
- **WHEN** one active hook has the configured URL, `config.content_type` `json`, and the events `issues`, `milestone`, `pull_request` and `release`
- **THEN** the row is `present`

#### Scenario: The hook does not send an event that the Service takes
- **WHEN** the only hook with the configured URL is active, has `json`, and sends `pull_request` and `release` only
- **THEN** the row is `wrong` and names `events`

### Requirement: No hooks is missing
The row SHALL report `missing` when the hooks list is empty.

#### Scenario: The repository has no hooks
- **WHEN** the hooks response holds an empty list
- **THEN** the row is `missing` and prints the setup step

### Requirement: A non-matching hook is wrong
The row SHALL report `wrong` and name the field when no active hook matches and the list is not empty. A hook whose URL only differs SHALL name `url`, `content_type` and `events` when those differ too.

#### Scenario: One hook has wrong fields
- **WHEN** the response holds one hook with another URL, another content type and another event set
- **THEN** the row is `wrong` and names `url`, `content_type` and `events`

### Requirement: An inactive Service hook is wrong
The row SHALL report `wrong` and name `active` when the only hook with the Service URL is inactive.

#### Scenario: The Service hook is inactive
- **WHEN** the response holds one inactive hook with the Service URL, `json` and the roadmap events
- **THEN** the row is `wrong` and names `active`

### Requirement: An unreadable hooks list does not fail
The row SHALL report `not readable as <login>` and print the step, and the command SHALL not fail for it.

#### Scenario: No administration read
- **WHEN** the hooks request answers 403
- **THEN** the row is `not readable as <login>` and the command exits 0

### Requirement: The step names the webhook and no secret
A missing or wrong row SHALL print `service.webhook_url`, the content type `application/json`, the roadmap events and `devops config set service.webhook_secrets`, and SHALL print no secret. The row SHALL create no hook.

#### Scenario: The step of a missing row
- **WHEN** the row is `missing`
- **THEN** the step names the URL, the content type, the events and the secret command

### Requirement: The document and the row name the same events
The events of `CONST_ROADMAP_WEBHOOK_EVENTS` SHALL equal the events that `docs/CLUSTER.md` step 8 names.

#### Scenario: Step 8 names the Issues event
- **WHEN** a test reads step 8 of `docs/CLUSTER.md`
- **THEN** the step names the Issues event and the constant holds only `issues`

## MODIFIED Requirements

### Requirement: One row for each prerequisite
`devops roadmap onboard` SHALL check seven prerequisites in the documented order and SHALL print one row for each, with its number, its state and any reason or step.

#### Scenario: A repository that holds every prerequisite
- **WHEN** the repository has issues turned on, the App installed, a valid labels file, every workflow label, the clear-status workflow, its place in `service.repos`, and one active webhook with the Service URL, the `json` content type and the roadmap events
- **THEN** every row is `present` and the command exits 0

## ADDED Requirements

### Requirement: The webhook row reads the repository hooks
The `webhook` row SHALL read `GET repos/<owner>/<name>/hooks` once and SHALL print a state.

#### Scenario: The row reads hooks
- **WHEN** the installation token can read hooks
- **THEN** the row sends one GET request to `repos/<owner>/<name>/hooks`

### Requirement: A matching hook is present
The row SHALL report `present` when one active hook has `service.webhook_url`, the content type `json`, and events equal to `CONST_ROADMAP_WEBHOOK_EVENTS`.

#### Scenario: One active hook matches
- **WHEN** one active hook has the configured URL, `config.content_type` `json`, and the roadmap events
- **THEN** the row is `present` and names no field

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

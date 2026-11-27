## ADDED Requirements

### Requirement: A default webhook URL is a person step
Row 12 SHALL report the state `person` with one step that names the setting `service.webhook_url` when the setting holds its default value. It SHALL send no request to a repository hooks route and SHALL plan no hook in that case.

#### Scenario: A default webhook URL plans no hook
- **WHEN** a test in `tests/commands/test_repos_onboard.py` runs `devops repos onboard example-org/app --plan` over the fake GitHub API with `service.webhook_url` at its default value
- **THEN** row 12 holds the state `person`, its step names `service.webhook_url`, the row holds no change, and the fake records no request to a hooks route

#### Scenario: A confirm with the default webhook URL writes no hook
- **WHEN** a test in `tests/commands/test_repos_onboard.py` runs `devops repos onboard example-org/app --confirm --only 12` over the fake GitHub API with `service.webhook_url` at its default value
- **THEN** the fake records no POST and no PATCH to a hooks route, and row 12 holds the state `person`

### Requirement: The step of a withheld secret says why
The step of a withheld secret SHALL name the reason (row 13 is not in `--only`, `--no-deploy`, or the refusal reason of the clean-checkout checks) and the command `devops repos onboard <repo> --confirm --only 12,13`, and SHALL name no deploy-stack.

#### Scenario: A withheld secret with no deploy
- **WHEN** a test in `tests/github/onboard/test_onboard_rows.py` runs a confirmed row 12 with an existing hook whose secret the map lacks and `--no-deploy`
- **THEN** the step of row 12 names `--no-deploy` and `--confirm --only 12,13`, and no step of the run names deploy-stack

### Requirement: The webhook secret write needs the Service row
Row 12 SHALL write a new secret to an existing hook only in a run that does row 13 with its deploy and passes the clean-checkout checks that row 13 makes. With `--no-deploy`, with row 13 out of `--only`, or with a checkout that row 13 refuses, it SHALL report the difference, write nothing, and give one step that names `service.webhook_secrets` and the reason.

#### Scenario: An existing hook with row 13 out of the run
- **WHEN** a test in `tests/github/onboard/test_onboard_rows.py` runs a confirmed row 12 with a set `service.webhook_url`, an existing hook whose secret the map lacks, and row 13 out of `--only`
- **THEN** the fake records no PATCH to the hook, row 12 holds the state `pending`, and its step names `service.webhook_secrets`

#### Scenario: An existing hook with no deploy
- **WHEN** a test in `tests/github/onboard/test_onboard_rows.py` runs a confirmed row 12 with an existing hook whose secret the map lacks and `--no-deploy`
- **THEN** the fake records no PATCH to the hook, and row 12 holds the state `pending`

#### Scenario: An existing hook with a refused row 13
- **WHEN** a test in `tests/github/onboard/test_onboard_rows.py` runs a confirmed run with an existing hook whose secret the map lacks and a devops-cli checkout whose `git status` lists one file
- **THEN** the fake records no PATCH to the hook, row 12 holds the state `pending`, its step names the changed file count, and row 13 is `refused`

#### Scenario: An existing hook with row 13 in the run
- **WHEN** a test in `tests/github/onboard/test_onboard_rows.py` runs a confirmed run with row 13 in `--only`, a set `service.webhook_url`, clean checkouts, and an existing hook whose secret the map lacks
- **THEN** the fake records one PATCH to the hook that carries the new secret, the map `service.webhook_secrets` holds that secret, and one `push-secrets` starts

## MODIFIED Requirements

### Requirement: The webhook row writes the hook and keeps its secret
Row 12 SHALL be `present` when one active hook has `service.webhook_url`, the content type `json`, each event of `CONST_ROADMAP_WEBHOOK_EVENTS` or `*`, and its secret in `service.webhook_secrets`. With `--confirm`, a missing hook SHALL get `POST` with a new secret that goes into the keyring map `service.webhook_secrets` and into no output. A wrong hook SHALL get `PATCH` with a new secret only in a run that does row 13 with its deploy.

#### Scenario: A hook that sends every event
- **WHEN** the hook sends `*` and the keyring map holds its secret
- **THEN** row 12 is `present`

#### Scenario: A new hook
- **WHEN** the repository has no hook and `--confirm` runs
- **THEN** the fake GitHub gets one `POST` of a hook, the keyring map holds the secret of the hook, and the output does not hold the secret

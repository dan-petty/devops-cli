## ADDED Requirements

### Requirement: request-plan-commands-list-planned-requests
A command with the request-plan class SHALL list its ordered PlannedRequest items under --dry-run and make no external request.

#### Scenario: dry-run prints plan
- **WHEN** a user runs devops <command> --dry-run or devops --dry-run <command> for a request-plan command
- **THEN** the output contains the ordered PlannedRequest items with argv, stdin, env placeholders, condition, and repeat, and no external request is made

#### Scenario: plan matches real run
- **WHEN** a test runs the real command against a fake runner or client that records each call
- **THEN** the recorded calls match the PlannedRequest list in order and content

### Requirement: local-preview-commands-print-change
A command with the no-external-request class that changes local state SHALL print the change and write nothing under --dry-run.

#### Scenario: preview prints and writes nothing
- **WHEN** a user runs devops mcp export-schemas --dry-run with the writer patched to fail
- **THEN** the output prints the change and no file is written

### Requirement: mark-only-commands-run-normally
A command with the no-external-request class that makes no external request SHALL run normally under devops --dry-run.

#### Scenario: mark-only runs under dry-run
- **WHEN** a user runs devops --dry-run mcp tools with the process runner and HTTP clients patched to fail
- **THEN** the command runs normally and returns its result

### Requirement: plan-built-from-same-builder
The PlannedRequest list of a request-plan command SHALL be built from the same argument builder that the real run uses.

#### Scenario: no drift between plan and run
- **WHEN** a test compares the PlannedRequest list with the calls recorded by a fake runner
- **THEN** the argv, stdin, env, condition, and repeat of each PlannedRequest match the recorded calls exactly

### Requirement: echo-only-previews-removed
A command that gains a request-plan or local-preview dry run SHALL have its echo-only preview removed.

#### Scenario: no echo-only preview remains
- **WHEN** the source of a command that gained a request-plan dry run is inspected
- **THEN** no render_dry_run_result call or @dry_run_command decorator remains for that command

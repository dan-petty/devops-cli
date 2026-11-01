## ADDED Requirements

### Requirement: request-plan-dry-run-returns-planned-requests
A command with the request-plan class SHALL make no external request under --dry-run and SHALL return its real result type marked as a dry run with the ordered PlannedRequest items.

#### Scenario: dry-run makes no external request
- **WHEN** a request-plan command is invoked with --dry-run and the process runner and HTTP clients are patched to raise
- **THEN** the command completes without raising and the output lists the ordered PlannedRequest items with argv, stdin, env, condition and repeat

#### Scenario: dry-run returns real result type as json
- **WHEN** a request-plan command is invoked with --dry-run and --format json
- **THEN** the JSON output has the dry-run mark and the planned requests array in order

### Requirement: no-external-request-runs-normally
A command with the no-external-request class SHALL run normally under devops --dry-run.

#### Scenario: dry-run runs the command
- **WHEN** a no-external-request command is invoked under devops --dry-run with the process runner and HTTP clients patched to raise
- **THEN** the command completes and returns its normal result without a dry-run mark

### Requirement: request-plan-matches-real-run
The PlannedRequest items of a request-plan dry run SHALL match the requests the real run makes, in the same order.

#### Scenario: plan matches recorded calls
- **WHEN** a test runs the real command against a fake runner or client that records each call and compares the calls with the plan
- **THEN** the recorded calls match the PlannedRequest items in order with the same argv, stdin and env

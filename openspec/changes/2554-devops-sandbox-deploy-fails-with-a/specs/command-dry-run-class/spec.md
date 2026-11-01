## MODIFIED Requirements

### Requirement: sandbox-request-plans
Nine commands in `sandbox` SHALL carry the `request-plan` dry-run class: `sandbox deploy`, `sandbox exec`, `sandbox logs`, `sandbox metrics`, `sandbox network-policy`, `sandbox probe`, `sandbox status`, `sandbox stop`, and `sandbox traces`.
Under dry run, each command SHALL make zero external requests, execute zero daemon socket calls, perform zero HTTP or DNS requests, and output its planned requests.
The planned requests of `sandbox deploy` SHALL include the image lookup and the image pull, in the order the real run sends them, before the container creation. The image pull SHALL carry the condition that the image is not on the engine.

#### Scenario: Dry run on sandbox deploy
- **WHEN** user executes `devops sandbox deploy --dry-run`
- **THEN** the command prints planned image lookup, conditional image pull, container creation and start requests, in that order, and makes zero engine calls

#### Scenario: Dry run on sandbox exec
- **WHEN** user executes `devops sandbox exec ls --dry-run`
- **THEN** the command prints planned exec requests and makes zero engine calls

#### Scenario: Dry run on sandbox probe
- **WHEN** user executes `devops sandbox probe --dry-run`
- **THEN** the command prints planned HTTP health probe requests and makes zero network calls

#### Scenario: Dry run on sandbox metrics
- **WHEN** user executes `devops sandbox metrics --dry-run`
- **THEN** the command prints planned Prometheus metrics endpoint requests and makes zero network calls

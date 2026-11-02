## ADDED Requirements

### Requirement: The job probes the premise at the staging commit
The stage job SHALL run bounded read-only probes at the staging commit for each path and identifier that the issue cites, before the model call.

#### Scenario: Probe output is in the model input
- **WHEN** The job plans an issue that cites a path and an identifier
- **THEN** The model input holds the probe output for the path and the identifier before the model call.

#### Scenario: A missing path names its removal commit
- **WHEN** The issue cites a path that the staging commit does not hold
- **THEN** The probe output names the commit that removed or moved the path.

#### Scenario: The bound stops the probes
- **WHEN** The issue cites more paths and identifiers than the bound allows
- **THEN** The probe stops at the bound and records the probes that it skipped.

### Requirement: A false premise returns the item
When the model reply holds `premise_failed` with evidence, the stage job SHALL run `devops roadmap return <issue> --comment <evidence> --confirm` and SHALL open no pull request.

#### Scenario: A false premise opens no pull request
- **WHEN** The model reply holds `premise_failed` with evidence
- **THEN** The job returns the item with the evidence and opens no pull request.

#### Scenario: A plan with a true premise opens the draft
- **WHEN** The model reply holds no `premise_failed`
- **THEN** The job writes the change and opens the draft pull request.

### Requirement: The Feasibility section quotes the probe output
The prompt of the stage job SHALL ask the `feasibility` section to quote the probe output.

#### Scenario: The prompt asks for the quote
- **WHEN** The stage job loads the prompt of the plan
- **THEN** The prompt asks `feasibility` to quote the probe output.

## ADDED Requirements

### Requirement: The implement agent runs the stock shell with no allowlist
The agent of an implement step SHALL run the `Shell` of `Coder` with no allowed command and no denied command, and SHALL add no capability that refuses a command by a policy of the project. The runner pod SHALL be the sandbox of the step.

#### Scenario: The agent of a step has the stock shell
- **WHEN** The test calls `build_agent` with a sentinel check list.
- **THEN** It finds a `Coder` whose `Shell` holds no allowed command and no denied command, and whose capabilities hold no refusal wrapper.

## REMOVED Requirements

### Requirement: The shell tool admits only the project's programs
**Reason**: The shell admits every program of the runner image, so no table of programs remains.
**Migration**: The implement agent runs the stock shell with no allowlist

### Requirement: The shell admits a read pipe and the checkout prefix
**Reason**: The harness reads the whole command, and the step adds no pipe reader and no checkout prefix.
**Migration**: The implement agent runs the stock shell with no allowlist

### Requirement: The shell of the agent refuses a command that starts with a bang
**Reason**: The shell refuses no command by a policy of the project, so no refusal text exists.
**Migration**: The implement agent runs the stock shell with no allowlist

### Requirement: The python -c refusal names the write_file call first
**Reason**: The shell refuses no python -c, so no hint names the write_file call.
**Migration**: The implement agent runs the stock shell with no allowlist

### Requirement: The implement prompt names the refusal of a heredoc
**Reason**: The prompt names the stock shell, which runs a heredoc.
**Migration**: The implement agent runs the stock shell with no allowlist

### Requirement: Consecutive refusals stop the step
**Reason**: The step counts no refusal and stops on no count of them.
**Migration**: The implement settings hold no refusal count

### Requirement: A chain of allowed programs names two calls
**Reason**: No allowlist remains, so a chain of programs gives no refusal.
**Migration**: The implement agent runs the stock shell with no allowlist

### Requirement: The pipe refusal names read_file
**Reason**: The shell refuses no pipe, so no hint names the read_file call.
**Migration**: The implement agent runs the stock shell with no allowlist

### Requirement: The refusal table names openspec and devops
**Reason**: The prompt holds no refusal table.
**Migration**: The implement agent runs the stock shell with no allowlist

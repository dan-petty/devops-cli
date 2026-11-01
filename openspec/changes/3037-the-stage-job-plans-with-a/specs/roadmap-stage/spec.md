## ADDED Requirements

### Requirement: Planner tool set is read-only
The stage job planner SHALL expose only read-only tools and SHALL NOT expose a write tool or a network tool.

#### Scenario: Tool set contains only read-only tools
- **WHEN** the planner starts a plan run in the scratch clone
- **THEN** the available tools are list files, read file, read line range, grep, git log, git show, AST graph, callers of symbol, devops ai repomap, and read base spec

### Requirement: Planner references only existing files
The stage job planner SHALL reference only file paths that exist in the scratch clone.

#### Scenario: Plan output references valid paths
- **WHEN** the planner completes a plan run
- **THEN** every file path in the plan output exists in the scratch clone

### Requirement: Plan run trace records tool calls
The trace of a plan run SHALL record every tool call with its arguments and the total token count.

#### Scenario: Trace contains tool calls and tokens
- **WHEN** a plan run completes
- **THEN** the trace lists each tool call with its arguments and the total token count

### Requirement: Plan run stops at budget
A plan run SHALL stop when the tool call count or token count reaches the budget limit, and SHALL record the limit that was hit in the trace.

#### Scenario: Budget exhaustion stops the run
- **WHEN** the tool call count reaches 30
- **THEN** the run stops and the trace records the call count limit

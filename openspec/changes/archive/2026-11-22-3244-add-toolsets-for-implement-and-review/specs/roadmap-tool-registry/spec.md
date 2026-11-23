## Purpose
One table of the tools that a roadmap job and an MCP role server may hold, with a toolset setting for each job and a check that every table name is an entry of the table.

## ADDED Requirements

### Requirement: One table holds the tools of every job and role
The project SHALL keep one tool registry in `src/devops_cli/roadmap/tools.py`, and each entry SHALL hold a name, a one-line purpose, a read-only flag and the tables that hold the tool.

#### Scenario: Entry fields
- **WHEN** a test reads every entry of the registry
- **THEN** each entry has a non-empty name, a one-line purpose, a boolean read-only flag and at least one table name

#### Scenario: One entry for each name
- **WHEN** a test reads the names of the registry
- **THEN** each name appears once and the table gives one purpose for it

### Requirement: The three jobs have a toolset setting
The settings `roadmap.stage.toolset`, `roadmap.implement.toolset` and `roadmap.review.toolset` SHALL exist, and the tools of each value SHALL come from the registry.

#### Scenario: The implement and review defaults are base
- **WHEN** a test reads the default of `roadmap.implement.toolset` and of `roadmap.review.toolset`
- **THEN** each value is `base`

#### Scenario: The implement base is the six step tools
- **WHEN** a test reads the names that the `implement` holder gives
- **THEN** the names are `read_file`, `write_file`, `edit_file`, `list_files`, `grep` and `shell`

#### Scenario: The stage setting keeps its two values
- **WHEN** a test reads `roadmap.stage.toolset`
- **THEN** `base` names the nine stage tools, and `extended` names those nine and `references`, `read_issue` and `find_issues`

#### Scenario: A value outside the setting is refused
- **WHEN** a config file or a variable sets an implement toolset other than `base`
- **THEN** the settings load fails and the message names the variable

### Requirement: A table name must be a registry entry
A test MUST fail when a role table or a toolset names a tool that the registry does not hold.

#### Scenario: Unknown tool name
- **WHEN** a role table or a toolset names a tool that is absent from the registry
- **THEN** the test fails and its message names the table and the missing tool

### Requirement: One table chooses the tools of each host
The stage toolset and the three job role tables SHALL read their names from the registry, and no second list of tool names SHALL remain in the roadmap jobs or in the MCP role tables.

#### Scenario: The stage tools
- **WHEN** a plan run asks for the tools of `base`
- **THEN** the tools are the methods that the `stage` holder names, in table order

#### Scenario: The role tables
- **WHEN** a role server lists the tools of its role
- **THEN** its table is the set of names that the registry gives for that role

#### Scenario: No name outside the registry
- **WHEN** a test compares every role table and every toolset value with the registry
- **THEN** no table holds a name that the registry lacks

## ADDED Requirements

### Requirement: A task group names each changed path in a code span
The stage content check MUST refuse a plan whose task group names a path of its `changes` nowhere in a backtick code span of its `implementation`, and its message MUST name every path that the implementation omits.

#### Scenario: One omitted path
- **WHEN** a group holds two paths in changes and its implementation names one of them in a code span
- **THEN** the check reports one problem that names the omitted path

#### Scenario: Two omitted paths
- **WHEN** a group holds three paths in changes and its implementation names one of them in a code span
- **THEN** the check reports one problem that names both omitted paths

#### Scenario: Eevery changed path named
- **WHEN** each path of changes is a code span of the implementation
- **THEN** the check reports no problem for the changed paths

### Requirement: The stage prompt asks for each changed path in a code span
The roadmap stage prompt MUST state that the implementation of a task group names every path of its changes in a backtick code span.

#### Scenario: The prompt states the changed-path rule
- **WHEN** the roadmap stage prompt is read
- **THEN** it states that the implementation of a task group names every path of its changes in a code span

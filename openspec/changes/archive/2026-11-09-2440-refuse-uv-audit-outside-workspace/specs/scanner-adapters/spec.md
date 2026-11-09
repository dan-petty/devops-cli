## ADDED Requirements

### Requirement: uv audit refuses a project outside the workspace
The uv audit adapter SHALL resolve the project that uv would audit from the target, and SHALL NOT start the audit when that project lies outside the workspace. It SHALL give the outcome `not_applicable`, with no finding, and a reason that names the directory of that project. It SHALL resolve the project with `uv workspace dir`, so the project is the one that uv would audit. It SHALL treat the working directory of the process as the workspace.

#### Scenario: The project is outside the workspace
- **WHEN** the uv audit adapter scans a subdirectory of a uv project, and the project that uv finds from that subdirectory lies in a parent of the workspace
- **THEN** the audit does not start, and the outcome is `not_applicable` with no finding and the reason `uv audit would audit the project at <project>, which lies outside the workspace. The scan audits only the project of the workspace.`

#### Scenario: The project is in the workspace
- **WHEN** the uv audit adapter scans a directory, and the project that uv finds from it lies in the workspace
- **THEN** the audit starts, and the outcome is the findings of the report of the project

#### Scenario: uv finds no project
- **WHEN** the uv audit adapter scans a directory, and uv finds no project from it or its parents
- **THEN** the audit starts, and the outcome is what the audit gives, as it is when there is no lockfile

#### Scenario: uv is not installed
- **WHEN** the uv audit adapter scans a directory, and no directory of PATH holds uv
- **THEN** the probe does not run, and the outcome is `unavailable`, as it is when the audit starts

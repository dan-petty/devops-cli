## MODIFIED Requirements

### Requirement: The map and the spec tools give short answers
`repo_map` SHALL give one line for each file of a directory, up to `CONST_ROADMAP_STAGE_MAP_MAX_FILES` files. `read_spec` SHALL read the specs with `openspec list --specs` and `openspec show --type spec`. For one capability it SHALL answer with a line `Purpose:`, each requirement name with its scenario names, and each requirement that another active change adds or modifies. It SHALL answer as text when OpenSpec is not installed.

#### Scenario: A directory with more files than the limit
- **WHEN** `repo_map` maps a directory of `CONST_ROADMAP_STAGE_MAP_MAX_FILES` plus 5 Python files
- **THEN** the answer has `CONST_ROADMAP_STAGE_MAP_MAX_FILES` file lines, each with the path and the names of the top-level symbols cut to 180 characters, and a last line that says that files are left out

#### Scenario: A requirement
- **WHEN** `read_spec` gets a capability and a requirement name
- **THEN** it answers with the heading, the text and the scenarios of that requirement

#### Scenario: A capability
- **WHEN** `read_spec` gets a capability and no requirement name, and the capability holds two requirements that each hold one scenario
- **THEN** it answers with a first line `Purpose:` and the purpose, and then the name of each requirement with the name of its scenario

#### Scenario: A capability with no requirement
- **WHEN** `read_spec` gets a capability that holds a purpose and no requirement
- **THEN** it answers with the line `Purpose:` and the purpose

#### Scenario: An active change modifies one requirement
- **WHEN** `read_spec` gets a capability, and an active change modifies a requirement of the capability
- **THEN** the answer names the change, the requirement and the name of its scenario

#### Scenario: A removed requirement is no candidate
- **WHEN** `read_spec` gets a capability, and an active change removes a requirement of the capability
- **THEN** the answer lists no requirement of that change

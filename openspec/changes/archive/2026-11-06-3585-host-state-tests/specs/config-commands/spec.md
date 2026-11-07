## ADDED Requirements

### Requirement: The project config search stops at a project root
The search for a project config file SHALL accept a file in the base directory. It SHALL accept a file in an ancestor directory only when that ancestor holds a `.git` or a `.devcontainer` entry, and it SHALL stop at the first such ancestor. The SSH key prefix search SHALL follow the same rule.

#### Scenario: Config file in an ancestor with no project marker
- **WHEN** a `config.yaml` is in the parent of the base directory, and the parent holds no `.git` and no `.devcontainer`
- **THEN** the search returns no project config file

#### Scenario: Config file in a project root
- **WHEN** a `config.yaml` is in the parent of the base directory, and the parent holds a `.git`
- **THEN** the search returns that file

#### Scenario: Key prefix with a stray config file
- **WHEN** a `config.yaml` that sets `ssh.key_prefix` is in an ancestor with no project marker, and no other source sets the prefix
- **THEN** the key prefix is the name of the workspace directory

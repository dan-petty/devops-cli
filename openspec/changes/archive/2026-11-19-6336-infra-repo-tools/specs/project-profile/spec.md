## ADDED Requirements

### Requirement: The profile names the install command of the tools
The project profile SHALL have the key `tools.install`, a list of arguments that installs the tools of the repository into its checkout. The type template `ansible-k8s` SHALL set it to `["make", "install"]`, and `.devops/project.toml` SHALL be able to replace it, also with an empty list.

#### Scenario: The template gives the command
- **WHEN** the profile of a repository with `ansible.cfg` and no project file is resolved
- **THEN** `tools.install` is `["make", "install"]` with the source `template: ansible-k8s`

#### Scenario: The project file turns the command off
- **WHEN** `.devops/project.toml` sets `[tools] install = []`
- **THEN** `tools.install` is empty with the source `.devops/project.toml`

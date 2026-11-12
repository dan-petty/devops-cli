# project-profile Specification

## Purpose
How devops-cli resolves the project profile of a repository: its type and the facts of its files, from the type template, detection and the project file `.devops/project.toml`, each value with its source.

## Requirements

### Requirement: Layers merge from defaults to the project file
`resolve_profile` SHALL merge, from low to high precedence, the field defaults of `ProjectProfile`, the packaged type template `templates/profiles/<type>.toml`, the facts that detection reads, and `.devops/project.toml`. A table SHALL merge by key, and a scalar or a list SHALL replace the lower value. Each value that a layer gives SHALL record that layer as its source.

#### Scenario: Detection with no project file
- **WHEN** a repository has `ansible.cfg` with an inventory and `roles_path`, a folder `ansible/playbooks` and a folder `k8s`, and no `.devops/project.toml`
- **THEN** the type is `ansible-k8s` from `detected: ansible.cfg`, the inventory and the role folders come from `ansible.cfg`, the playbook folder is `ansible/playbooks`, the Kubernetes folder is `k8s`, and the offline group `offline` comes from `template: ansible-k8s`

#### Scenario: The project file wins
- **WHEN** `.devops/project.toml` sets `[ansible] offline_group = "retired"`
- **THEN** the offline group is `retired` with the source `.devops/project.toml`, and the other values keep their sources

### Requirement: Detection keeps paths in the repository
Detection SHALL read the inventory and `roles_path` of `ansible.cfg` relative to the file, and SHALL keep only paths in the repository. It SHALL leave out a role folder that does not exist.

#### Scenario: A roles path outside the repository
- **WHEN** `roles_path` is `ansible/roles:./roles:../roles` and only `ansible/roles` exists
- **THEN** the role folders are `ansible/roles`

### Requirement: The values to declare
The resolved profile SHALL give each value that differs from the type template, so that a project file can declare it.

#### Scenario: A detected profile
- **WHEN** the profile of a repository with no project file is resolved
- **THEN** the values to declare are the type, the inventory, the playbook folder, the role folders and the Kubernetes folder, and not the offline group of the template

### Requirement: An invalid project file is refused
`resolve_profile` SHALL raise `ConfigurationError` with the key `.devops/project.toml` when the file is not TOML, names an unknown type or holds an unknown key.

#### Scenario: An unknown type
- **WHEN** `.devops/project.toml` sets `extends = "cobol"`
- **THEN** `ConfigurationError` names `.devops/project.toml`

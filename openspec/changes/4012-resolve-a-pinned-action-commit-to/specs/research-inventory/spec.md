## MODIFIED Requirements

### Requirement: The inventory lists each pin as a typed component
`devops research inventory` SHALL read the pins in `pyproject.toml`, `uv.lock`, the tools lock, the Node lock files, the Dockfiles, the devcontainer lock, the workflows and composite actions of `.github/`, the YAML files under `k8s/` and the Teraform files under `tf/`. It SHALL list one component for each pin, with its kind, ecosystem, name, version, file and line and, for an Action pin whose ref is a commit, that commit, ordered by file, then line, then name.

#### Scenario: Each kind of pin gives a component
- **WHEN** the repository holds one pin of each kind in the formats above
- **THEN** the list holds the components of the expected kind, name, version, file and line, and no other

#### Scenario: The same action at two versions
- **WHEN** two workflow steps use `astral-sh/setup-uv` at two releases
- **THEN** the list holds two components for it, one for each release and line

#### Scenario: A pinned action shows its release
- **WHEN** a step reads `uses: actions/checkout@<commit> # v7`
- **THEN** the version of the component is `v7` and the component holds the commit

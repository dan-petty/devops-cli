## MODIFIED Requirements

### Requirement: The inventory lists each pin as a typed component
`devops research inventory` SHALL read the pins in `pyproject.toml`, `uv.lock`, the root `package-lock.json`, the Dockerfiles, the devcontainer lock, the workflows and actions of `.github/`, the YAML of `k8s/` and the Terraform of `tf/`. It SHALL list one component for each pin, with a kind, an ecosystem, a name, a version, the file from the repository root and the line, ordered by file, then line, then name.

#### Scenario: Each kind of pin gives a component
- **WHEN** the repository holds one pin of each kind in the formats above
- **THEN** the list holds the components of the expected kind, name, version, file and line, and no other

#### Scenario: A package of the root lockfile
- **WHEN** the `package-lock.json` at the root of the repository pins the devDependency `example-dev-tool` at `2.1.0`
- **THEN** the list holds a `node-package` component of the `npm` ecosystem with that name and version, the file `package-lock.json` and the line of its key

#### Scenario: The same action at two versions
- **WHEN** two workflow steps use `astral-sh/setup-uv` at two releases
- **THEN** the list holds two components for it, one for each release and line

#### Scenario: A pinned action shows its release
- **WHEN** a step reads `uses: actions/checkout@<commit> # v7`
- **THEN** the version of the component is `v7`

## REMOVED Requirements

### Requirement: A pin with no ecosystem is listed and counted
**Reason**: Its scenario read a binary of the tools lock, which is gone (#4363).
**Migration**: The requirement below reads an external pin of the watch file.

## ADDED Requirements

### Requirement: A pin with no publisher is listed and counted
A component that the reader cannot map to a registry SHALL have the ecosystem `unknown`. The summary SHALL count it in `unknown`, and the total SHALL include it.

#### Scenario: A pin outside the repository with no publisher
- **WHEN** the watch file declares a `[[pin]]` that names no repository and no OSV identity
- **THEN** the mapped inventory holds it with the ecosystem `unknown` and the summary counts one unknown component

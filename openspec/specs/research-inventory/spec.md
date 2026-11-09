# research-inventory Specification

## Purpose
How `devops research inventory` reads the pins of a repository from its files into one typed list of components, with a count of each kind and each ecosystem, and without a model, a network request or a started program.

## Requirements

### Requirement: The inventory lists each pin as a typed component
`devops research inventory` SHALL read the pins in `pyproject.toml`, `uv.lock`, the tools lock and its requirement and Node lock files, the Dockerfiles, the devcontainer lock, the workflows and composite actions of `.github/`, the YAML files under `k8s/` and the Terraform files under `tf/`. It SHALL list one component for each pin, with a kind, an ecosystem, a name, a version, the file from the repository root and the line, ordered by file, then line, then name.

#### Scenario: Each kind of pin gives a component
- **WHEN** the repository holds one pin of each kind in the formats above
- **THEN** the list holds the components of the expected kind, name, version, file and line, and no other

#### Scenario: The same action at two versions
- **WHEN** two workflow steps use `astral-sh/setup-uv` at two releases
- **THEN** the list holds two components for it, one for each release and line

#### Scenario: A pinned action shows its release
- **WHEN** a step reads `uses: actions/checkout@<commit> # v7`
- **THEN** the version of the component is `v7`

### Requirement: A pin with no ecosystem is listed and counted
A component that the reader cannot map to a registry SHALL have the ecosystem `unknown`. The summary SHALL count it in `unknown`, and the total SHALL include it.

#### Scenario: A tool from a source that is no GitHub repository
- **WHEN** a binary tool of the tools lock names a `source` outside `github.com`
- **THEN** the list holds it with the ecosystem `unknown` and the summary counts one unknown component

### Requirement: The reader reaches nothing outside the files
The inventory SHALL start no program and open no network connection.

#### Scenario: Programs and sockets refuse
- **WHEN** the inventory reads a repository while a program start and a socket connection fail
- **THEN** the inventory is read in full

### Requirement: A file that does not parse stops the run
When a file does not parse, the inventory SHALL raise `InventoryError` (`RESEARCH_INVENTORY_ERROR`, exit code 1) with the path of the file.

#### Scenario: A broken pyproject.toml
- **WHEN** `pyproject.toml` is not valid TOML
- **THEN** the command fails with `RESEARCH_INVENTORY_ERROR` and the message names `pyproject.toml`

### Requirement: The command prints the list and the summary
The command SHALL print a table, or with `--json` or `--format yaml` the components and a summary with the total, the unknown count and the count of each kind and each ecosystem. It SHALL have the `no-external-request` dry-run class and an MCP tool that takes no argument.

#### Scenario: JSON output
- **WHEN** `devops research inventory --root <repository> --json` runs
- **THEN** the output is the JSON of the inventory of that repository

#### Scenario: The real repository
- **WHEN** the inventory reads the repository of devops-cli
- **THEN** it holds at least one component of every kind, and every component has a line and a version

### Requirement: The inventory reads the lock of each devcontainer configuration folder
`devops research inventory` SHALL read the devcontainer lock `.devcontainer/devcontainer-lock.json` and the lock `.devcontainer/<folder>/devcontainer-lock.json` of each configuration folder, and SHALL name the file of each feature pin from the repository root.

#### Scenario: A lock in a configuration folder
- **WHEN** a repository has only `.devcontainer/image/devcontainer-lock.json`, which pins one feature
- **THEN** the inventory lists one devcontainer feature component
- **AND** its file is `.devcontainer/image/devcontainer-lock.json` and its line is the line of the feature key

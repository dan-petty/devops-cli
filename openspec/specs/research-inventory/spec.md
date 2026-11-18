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
The inventory SHALL start no program and open no network connection unless the opt-in render option of `devops research inventory` is set and the run is not a dry run.

#### Scenario: Programs and sockets refuse
- **WHEN** the inventory reads a repository while a program start and a socket connection fail
- **THEN** the inventory is read in full

#### Scenario: Default inventory run
- **WHEN** a test runs `mapped_inventory` with no renderer
- **THEN** no program starts, no socket connection opens, and the run lists the components of the files alone

#### Scenario: Render in a dry run
- **WHEN** `devops research inventory --render --dry-run` runs
- **THEN** the command lists the pins of the files, builds no renderer, starts no program and opens no connection

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

### Requirement: Mapped OSV identity
The inventory SHALL read `.devops/research-watch.toml` and SHALL set the OSV ecosystem and the OSV name of a component from the `[[watch]]` entry that names the component's inventory ecosystem and name, when the entry gives them.

#### Scenario: Mapped component
- **WHEN** the mapping file names a component by its inventory ecosystem and name, gives its OSV ecosystem and name, and the repository holds a matching pin
- **THEN** `mapped_inventory` gives the component the mapped OSV ecosystem and name, and the summary counts it

### Requirement: Extra pin of the mapping file
The inventory SHALL list each pin that `.devops/research-watch.toml` declares in a `[[pin]]` entry, with the declared kind, ecosystem, name, version and upstream repository, at the file `external` and line 0, and with an empty version when the entry declares none.

#### Scenario: External pin
- **WHEN** the mapping file declares a pin with a kind, a name and a repository
- **THEN** `apply_mapping` lists the pin with those values at the file `external` and line 0, and the summary counts it

### Requirement: Package purl
The inventory SHALL set the purl of a package component with `PackageURL` of `packageurl-python` when its ecosystem, its name and its version give one, and SHALL leave the purl empty otherwise.

#### Scenario: Package purl
- **WHEN** a Python package pin has a name and a version
- **THEN** `purl_of` gives a purl that `PackageURL.from_string` reads back to the type pypi and to the name and the version of the pin

### Requirement: Registry reference
The inventory SHALL set the registry reference of a container image component to the registry host that serves its name, and to `docker.io` when the name holds no registry.

#### Scenario: Registry reference of an image
- **WHEN** an image pin names an image of the registry ghcr.io
- **THEN** `registry_of` gives the registry reference ghcr.io

### Requirement: Upstream repository
The inventory SHALL set the upstream repository of a component from the `repo` of the `[[watch]]` entry that names it or of the `[[pin]]` entry that declares it, and SHALL leave it empty when neither gives one.

#### Scenario: Mapped repository
- **WHEN** a mapping entry or an extra pin gives a repository for a component of the inventory
- **THEN** `apply_mapping` gives the component that repository value

### Requirement: Opt-in render
The inventory SHALL list each image of the rendered Argo CD Applications when the opt-in render option of `devops research inventory` is set, with the renderer of `devops k8s image-pins`.

#### Scenario: Rendered image
- **WHEN** the opt-in render option is set and a fake renderer returns an image that only the rendered chart names
- **THEN** `renderer_for` gives that image, `mapped_inventory` lists it as a container image at the file `rendered` and line 0, and the fake ran once

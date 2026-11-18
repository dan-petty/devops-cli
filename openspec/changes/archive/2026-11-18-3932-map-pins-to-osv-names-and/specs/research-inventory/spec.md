## ADDED Requirements

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

## MODIFIED Requirements

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

## Purpose
The project digest is a run-time record of the facts that describe this repository: its commands, its settings, its pinned versions, its architecture and its decision records, each read from its owner and never typed. A model reads the digest through a tool and through the knowledge base index.

## ADDED Requirements

### Requirement: The digest lists every command and every settings section
The digest SHALL list each command that the command tree registers, with its group and its help text, and each section and field of the settings model, with the field's name, its annotation, and the model's own default or the name of its default factory. The digest MUST hold no command that the tree does not register, and MUST hold no resolved value of a setting.

#### Scenario: A registered command, a settings field and an absent command
- **WHEN** A test builds the digest from the live command tree and the settings model, and asks for a command name that no module registers.
- **THEN** The behavior test asserts that the digest holds each registered command, each settings section and field with its model default or factory name, and no absent command.

### Requirement: Each pin comes from the file that owns it
The digest SHALL read each pinned version from the uv lock, the tools lock or the project manifest, and SHALL name the file that holds it. The digest MUST copy no version from prose.

#### Scenario: A changed lock changes the digest
- **WHEN** A test copies `pyproject.toml` and `uv.lock` into a temporary root, changes one version in the copy and builds the digest over that root.
- **THEN** The behavior test asserts that the digest shows the new version, names the uv lock as its file, and carries a content hash other than the hash of the digest over the unchanged root.

### Requirement: The digest lists the repository map and the decision records
The digest SHALL hold each module path of the repository map with its symbol count, each import edge of the import graph, and each decision record with its title and its front-matter status.

#### Scenario: Map, edges and decision records
- **WHEN** A test builds the digest for this repository and reads the records under `docs/adr`.
- **THEN** The behavior test asserts that the module paths equal the paths of the repository map, that each edge names two mapped modules, and that each record appears with its title and its status.

### Requirement: The digest carries its content hash and its commit
The digest SHALL carry a SHA-256 hash of its own sections and the full commit SHA that its build was given.

#### Scenario: Provenance fields
- **WHEN** A test builds the digest twice over one section map and once over a map with one changed section, with a fixed 40-character commit.
- **THEN** The behavior test asserts that the two equal builds carry one hash, that the changed map carries another hash, and that the digest carries the commit it was given.

#### Scenario: The head commit of the checkout
- **WHEN** A test calls `head_commit` with the process seam doubled to answer one SHA.
- **THEN** The behavior test asserts that the call asks the seam for `git rev-parse HEAD` and returns that SHA.

### Requirement: A model reads the digest through the tool and the index
The digest SHALL be reachable by a model through the `project_digest` tool and through the project digest section of the knowledge base index page, and both SHALL name the same digest sections.

#### Scenario: Tool and index section
- **WHEN** A test calls the `project_digest` tool and generates the knowledge base index.
- **THEN** The behavior test asserts that the index section names each section that the tool returns, and that the tool returns the content hash and the commit.

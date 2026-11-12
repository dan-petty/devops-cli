# ast-support Specification

## Purpose
Extracts and maps polyglot AST symbols from Kubernetes manifests, Helm templates, and Dockerfiles for code intelligence and repository maps.

## Requirements

### Requirement: Kubernetes manifest resource symbol extraction
The system SHALL parse YAML files and extract Kubernetes resource kind and name symbols from documents declaring a resource.

#### Scenario: Kubernetes manifest emits resource symbol
- **WHEN** the AST engine parses a YAML Kubernetes manifest with kind and metadata name
- **THEN** it emits a struct symbol named with the resource kind and name separated by a slash

### Requirement: Helm template define block symbol extraction
The system SHALL parse Helm template files and extract named template symbols from define blocks.

#### Scenario: Helm template emits define block symbols
- **WHEN** the AST engine parses a Helm template file containing define blocks
- **THEN** it emits function symbols for each define block matching the declared template name

### Requirement: Dockerfile stage and FROM image symbol extraction
The system SHALL parse Dockerfiles and extract symbols for build stages and FROM base images.

#### Scenario: Dockerfile emits stage and FROM image symbols
- **WHEN** the AST engine parses a Dockerfile with FROM instructions
- **THEN** it emits symbols for each stage alias and base image specification

### Requirement: The code graph walk skips each ignored folder
`devops ai ast graph` SHALL list the files of its folder in one walk. The walk SHALL NOT list `.git`, a folder that git ignores, or a folder in one of them.

#### Scenario: A folder that .gitignore names
- **WHEN** the graph is built for a folder that holds `.git`, a `.gitignore` that names `vendor/`, a Python file in `vendor/pkg/` and a Python file at the top
- **THEN** the walk lists only the top folder, and the graph indexes only the file at the top

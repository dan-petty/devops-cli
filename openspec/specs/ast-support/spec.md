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

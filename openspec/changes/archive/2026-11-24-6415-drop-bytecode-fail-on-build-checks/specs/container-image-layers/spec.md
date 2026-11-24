# container-image-layers Specification Delta

## ADDED Requirements

### Requirement: Build context drops bytecode and root Dockerfile enables build checks
The root `.dockerignore` SHALL exclude `__pycache__` directories and loose `.pyc` and `.pyo` files from the build context. The root `Dockerfile` SHALL set `# check=error=true` as a parser directive directly under the syntax directive.

#### Scenario: The root build enforces build checks
- **WHEN** a person reads line 2 of `Dockerfile`
- **THEN** line 2 holds `# check=error=true`

#### Scenario: The build context excludes bytecode
- **WHEN** `.dockerignore` is inspected
- **THEN** it excludes `**/__pycache__`, `**/*.pyc`, and `**/*.pyo` after `!src/**`

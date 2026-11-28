## ADDED Requirements

### Requirement: Trivy config scan skips virtual environments
`TrivyConfigScanner.build_command` SHALL pass `--skip-dirs .venv` and `--skip-dirs **/.venv` so `trivy config` skips root and nested `.venv` directories when scanning a checkout.

#### Scenario: Config scan arguments exclude virtualenv directories
- **WHEN** `TrivyConfigScanner().build_command(target, cwd=target)` builds arguments for a configuration scan
- **THEN** the argument list includes `--skip-dirs` for `.venv` and `**/.venv`, while `TrivyScanner().build_command(target, cwd=target)` adds neither

## REMOVED Requirements

### Requirement: The harbor template Dockerfile holds a dated ignore entry
**Reason**: `TrivyConfigScanner` now skips `.venv` directories via `--skip-dirs`, so third-party Harbor Dockerfiles under `.venv/` are no longer scanned and require no `.trivyignore.yaml` entry.

### Requirement: Dated ignore entry for the harbor template Dockerfile
**Reason**: `TrivyConfigScanner` now skips `.venv` directories via `--skip-dirs`, so third-party Harbor Dockerfiles under `.venv/` are no longer scanned and require no `.trivyignore.yaml` entry.

### Requirement: The entry carries an expiry that the scan reads
**Reason**: `TrivyConfigScanner` now skips `.venv` directories via `--skip-dirs`, so the Harbor `.venv/` entry in `.trivyignore.yaml` has been removed.

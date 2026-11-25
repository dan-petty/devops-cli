# toolchain-preset Specification

## Purpose
The implement job runs toolchain checks that match the configuration of each target repository.

## Requirements

### Requirement: Toolchain preset read
The implement job SHALL take the toolchain preset from `[project] toolchain` in `.devops/roadmap.toml`, read at `origin/<default>`.

#### Scenario: The file names a preset
- **WHEN** the trusted read of `.devops/roadmap.toml` holds `toolchain = "devops-cli"`
- **THEN** `resolve_profile` returns the `devops-cli` preset.

### Requirement: Default preset neutral
A repository with no `.devops/roadmap.toml` MUST get the `neutral` preset.

#### Scenario: No profile file
- **WHEN** the trusted read finds no `.devops/roadmap.toml`
- **THEN** the resolved profile names `neutral`, and its scoped checks hold no argv that names `uv` or `devops ci`.

### Requirement: devops-cli parity
The `devops-cli` preset MUST give the scoped checks, the docs step, the archive argv and the step gates that this repository has today.

#### Scenario: This repository's preset
- **WHEN** the profile resolves to `devops-cli`
- **THEN** the scoped checks, docs step, archive argv and step gates equal the values of today.

### Requirement: neutral scoped checks
A `neutral` profile MUST run only the pre-push hook check, with no static check and no test command.

#### Scenario: A neutral repository with hooks
- **WHEN** the profile is `neutral` and the target declares pre-push hooks
- **THEN** `scoped_checks` holds the pre-push hook check and no other check.

### Requirement: Unknown preset refused
A toolchain name that no preset holds MUST raise `ConfigurationError` that names the file.

#### Scenario: An unknown preset name
- **WHEN** `.devops/roadmap.toml` holds `toolchain = "cargo"`
- **THEN** `resolve_profile` raises `ConfigurationError` whose message holds `.devops/roadmap.toml`.

### Requirement: Docs step gated
The docs step SHALL run only when the preset declares a docs step.

#### Scenario: A neutral profile
- **WHEN** the profile is `neutral`
- **THEN** the job runs no docs step.

### Requirement: Archive step gated
The archive step MUST run only when `uses_openspec` is true, with the `archive_argv` of the preset.

#### Scenario: A neutral repository that uses OpenSpec
- **WHEN** the profile is `neutral` and `uses_openspec` is true
- **THEN** the archive step runs `openspec archive <change> --yes`.

### Requirement: Step gates gated
The `ruff format`, `ruff check` and `mypy` step gates MUST run only when the preset sets `step_gates = ruff-mypy`.

#### Scenario: A neutral profile with a changed Python file
- **WHEN** the profile is `neutral` and a step changes a Python file
- **THEN** the step runs no `ruff` command and no `mypy` command.

### Requirement: implement-steps removed
The `[implement.steps]` key MUST be gone from the code and the documents, with no shim.

#### Scenario: A search for the key
- **WHEN** `git grep -n 'implement.steps' src docs` runs
- **THEN** it finds no line.

### Requirement: devops-cli declares preset
This repository's `.devops/roadmap.toml` MUST declare `toolchain = "devops-cli"`.

#### Scenario: This repository's profile file
- **WHEN** the test reads `.devops/roadmap.toml`
- **THEN** `[project] toolchain` is `devops-cli`, and `[implement.steps]` is absent.

### Requirement: The roadmap file holds a review table
`resolve_profile` SHALL accept the `[review]` table in `.devops/roadmap.toml`, so a repository that configures `[review] tag_pattern` keeps a valid profile for the implement job.

#### Scenario: A roadmap file with a review table
- **WHEN** a commit holds `.devops/roadmap.toml` with `[project]` and `[review] tag_pattern = "release-*"`
- **THEN** `resolve_profile` returns the preset of `[project]` with no error

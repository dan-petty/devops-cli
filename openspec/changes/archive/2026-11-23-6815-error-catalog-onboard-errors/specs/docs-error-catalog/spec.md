## Purpose
The error catalog, `docs/ERRORS.md`, is the generated table of the `DevOpsCLIError` subclasses of devops-cli, with the error code, the exit status, the domain and the description of each. `devops docs generate` writes it.

## ADDED Requirements

### Requirement: The error catalog lists every error class of devops-cli
`devops docs generate` SHALL import the module of each `.py` file under the `devops_cli` package before it reads the `DevOpsCLIError` subclasses, with no list of modules that a person keeps. `docs/ERRORS.md` SHALL hold one row for each subclass that a module of devops-cli defines, whatever modules the process imported before.

#### Scenario: Each module is loaded after the import step
- **WHEN** a fresh interpreter runs the import step of the generator
- **THEN** the module of each `.py` file of the package is loaded, so a later import adds no `DevOpsCLIError` subclass, such as `AnswerFlagError` of `devops_cli.github.onboard.baseline`

#### Scenario: The catalog after another test
- **WHEN** the catalog test compares the error classes with the rows of `docs/ERRORS.md` alone, and after the tests of `tests/github/onboard/test_onboard_routes.py` in one process
- **THEN** both runs pass

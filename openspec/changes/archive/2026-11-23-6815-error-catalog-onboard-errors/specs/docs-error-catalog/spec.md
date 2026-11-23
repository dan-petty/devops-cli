## Purpose
The error catalog, `docs/ERRORS.md`, is the generated table of the `DevOpsCLIError` subclasses of devops-cli. Each row gives the error code, the exit status, the domain and the description of a subclass. `devops docs generate` writes it.

## ADDED Requirements

### Requirement: The error catalog lists every error class of devops-cli
`devops docs generate` SHALL import the module of each `.py` file under the `devops_cli` package before it reads the `DevOpsCLIError` subclasses, with no list of modules that a person keeps. `docs/ERRORS.md` SHALL hold one row for each subclass that a module of devops-cli defines, whatever modules the process imported before.

#### Scenario: The import step names the module of each source file
- **WHEN** the generator gives the module names of its import step
- **THEN** the names hold the module of each `.py` file of the package, such as `devops_cli.github.onboard.baseline` and the modules of `devops_cli.docker`

#### Scenario: The catalog after another test
- **WHEN** the catalog test compares the error classes with the rows of `docs/ERRORS.md` alone, and after the tests of `tests/github/onboard/test_onboard_routes.py` in one process
- **THEN** both runs pass

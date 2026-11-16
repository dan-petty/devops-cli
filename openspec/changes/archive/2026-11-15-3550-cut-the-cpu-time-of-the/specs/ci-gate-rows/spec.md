## ADDED Requirements

### Requirement: A CLI start loads no pydantic and only the help catalog
A fresh interpreter that imports `devops_cli.dry_run.state` SHALL load neither `devops_cli.dry_run.models` nor `pydantic`. A fresh interpreter that imports `devops_cli.main` SHALL load no `pydantic` and SHALL build `devops_cli.lang.en.help` alone, with no `devops_cli.lang.en.messages` and no `devops_cli.lang.en.errors`.

#### Scenario: A start that imports the dry-run state
- **WHEN** a fresh interpreter imports `devops_cli.dry_run.state`
- **THEN** `devops_cli.dry_run.models` and `pydantic` are not in its modules

#### Scenario: A start that imports the CLI main
- **WHEN** a fresh interpreter imports `devops_cli.main`
- **THEN** `pydantic` is not in its modules

#### Scenario: A start that builds the help catalog
- **WHEN** a fresh interpreter imports `devops_cli.main`
- **THEN** `devops_cli.lang.en.messages` and `devops_cli.lang.en.errors` are not in its modules and `devops_cli.lang.en.help` is

## MODIFIED Requirements

### Requirement: The startup-import row keeps its budgets and its control
The `startup-imports` row SHALL start each argv in a fresh interpreter under `-X importtime`, SHALL keep the four module limits, and SHALL fail when a run imports a heavy package. It SHALL name the ten slowest imports of a failed run, and it SHALL report the child CPU time of each probe on its own line. It SHALL fail when the root help leaves `pydantic` loaded.

#### Scenario: The control
- **WHEN** the root help runs after an import of a heavy package
- **THEN** the probe reports a heavy module and a count over the limit, and the row counts the control as passed

#### Scenario: A failed run
- **WHEN** a help argv imports a heavy module
- **THEN** the finding names the module and lists the ten slowest imports

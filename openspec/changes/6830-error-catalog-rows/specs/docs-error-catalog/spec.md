## ADDED Requirements

### Requirement: The catalog rows give the whole description and the area
Each row of `docs/ERRORS.md` SHALL give the whole first paragraph of the docstring of its class on one line, and SHALL escape each bar in it. The domain of a row SHALL be the area of devops-cli, the first name below the package, and never a module path.

#### Scenario: A docstring that wraps its first sentence
- **WHEN** the docstring of a class wraps its first sentence over two lines
- **THEN** the row gives the whole sentence on one line

#### Scenario: A class outside the exceptions package
- **WHEN** a class is defined in `devops_cli.github.onboard.baseline`
- **THEN** the domain of its row is `Github`

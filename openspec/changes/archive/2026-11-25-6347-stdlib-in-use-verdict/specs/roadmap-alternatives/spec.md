## ADDED Requirements

### Requirement: Standard library of a used language counts as in-use

`Inventory.uses` MUST return `True` when a tool's upstream project is the standard library of a language signaled either by a package PURL type in the repository SBOM or by a deployed file suffix under `config.inventory_paths`, without calling `deps.dev`. Third-party packages in that ecosystem MUST NOT match through this rule, and a repository with no matching package PURL or deployed suffix MUST NOT mark the standard library as in use.

#### Scenario: Standard library of a used language gets in-use
- **WHEN** the repository SBOM holds `pkg:pypi/httpx` and the model proposes `https://github.com/python/cpython` (`covers` or `partly`)
- **THEN** `Inventory.uses` returns `True` without calling `deps.dev` and the verdict becomes `in-use`

#### Scenario: Standard library gets in-use from a deployed suffix with empty SBOM
- **WHEN** the repository SBOM is empty, a deployed path holds a `.py` file, and the model proposes `https://github.com/python/cpython`
- **THEN** `Inventory.uses` returns `True` without calling `deps.dev` and the verdict becomes `in-use`

#### Scenario: Third-party tool keeps covers
- **WHEN** the repository SBOM holds only `pkg:pypi/httpx` and the model proposes `https://github.com/sqlalchemy/sqlalchemy` as `covers`
- **THEN** the standard library rule does not match and the verdict stays `covers`

#### Scenario: No standard-library rule without a language signal
- **WHEN** the repository SBOM is empty, no deployed path has a matching suffix, and the model proposes `https://github.com/python/cpython` as `covers`
- **THEN** `Inventory.uses` returns `False` and the verdict stays `covers`

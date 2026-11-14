## MODIFIED Requirements

### Requirement: Every caller imports a roadmap module by its path
Every import of a roadmap module under `src/`, and every import in `tests/` that runs, SHALL name the module path in the package. An import in an `if TYPE_CHECKING:` block of `tests/` is out of scope.

#### Scenario: No old roadmap module path remains
- **WHEN** `mypy --strict` checks `src/` and pytest collects and runs `tests/`
- **THEN** mypy reports no `import-not-found` or `attr-defined` error for `devops_cli.roadmap`, and no test fails on an import of a roadmap module.

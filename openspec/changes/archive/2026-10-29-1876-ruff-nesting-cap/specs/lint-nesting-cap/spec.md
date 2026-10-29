## Purpose

How the project caps the nesting of a function: Ruff's PLR1702 at 4 blocks, run through explicit lint preview by the same `ruff check` as every other rule, and with no nesting figure in `devops scan complexity` or `devops ai spec`.

## ADDED Requirements

### Requirement: Ruff caps a function at 4 nested blocks
The repository's Ruff configuration SHALL select `PLR1702` with `max-nested-blocks = 4`, so `ruff check --config pyproject.toml` fails a function whose innermost statement sits inside five nested blocks.

#### Scenario: Five and four nested blocks
- **WHEN** `ruff check --config pyproject.toml` lints, with the repository's Ruff table, one function with five nested `if` blocks and one with four
- **THEN** it reports `PLR1702` for the first function only

### Requirement: Only the named preview rules run, and the formatter stays stable
The Ruff configuration SHALL enable lint preview with `explicit-preview-rules = true` and SHALL leave the formatter out of preview.

#### Scenario: The resolved settings
- **WHEN** `ruff check --config pyproject.toml --show-settings` resolves the repository's settings
- **THEN** it shows `linter.preview = enabled`, `linter.explicit_preview_rules = true`, `linter.pylint.max_nested_blocks = 4`, `formatter.preview = disabled`, and `PLR1702` among the enabled rules

### Requirement: The complexity scan reports no nesting depth
`devops scan complexity` SHALL report functions over the complexity cap only, and SHALL have no option for a nesting depth.

#### Scenario: A deep function over the complexity cap
- **WHEN** the scan reads a function with six nested `if` blocks and a complexity of 7, with `max_complexity` 2
- **THEN** it reports one finding, for the complexity, and none for the nesting

#### Scenario: The removed option
- **WHEN** `devops scan complexity <path> --max-indent 5` runs
- **THEN** it exits 2 with a usage error

### Requirement: The architecture spec verifier has no indentation rule
`devops ai spec` SHALL record one forbidden-import rule for each source file, passed when the file imports no forbidden module, and SHALL record no rule for nesting depth.

#### Scenario: A deep function with no forbidden import
- **WHEN** the verifier reads a source file with six nested `if` blocks and no forbidden import
- **THEN** its report holds one passed `forbidden_import` rule for that file and no other rule

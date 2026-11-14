## Purpose
The `registries` subcommand of the `roadmap` group lists the registry and ratchet declarations of the test modules, checks each declaration and reports a ratchet assertion that no declaration covers.

## ADDED Requirements

### Requirement: The audit lists each declared registry entry
The `registries` subcommand of the `roadmap` group SHALL print each declared registry entry with its token, its kind, its target path and its source `path:line`.

#### Scenario: One declared entry
- **WHEN** A test module of the tests folder holds one `REGISTRY_COUNTS` entry and the command runs on that tree.
- **THEN** The output holds one row with the token, the kind, the target path and the source `path:line` of that entry.

### Requirement: The audit reads the test modules without importing one
The audit SHALL read each module-level `REGISTRY_COUNTS` declaration with `ast` and MUST NOT import a test module.

#### Scenario: A test module that fails at import
- **WHEN** A test module of the tests folder holds a declaration and raises an error at import time.
- **THEN** The audit lists the entry of that module and the command exits 0.

### Requirement: The audit lists the declarations of the test tree
The audit SHALL list every module-level `REGISTRY_COUNTS` declaration under the `tests` folder of the checkout that it reads.

#### Scenario: The four declaring modules
- **WHEN** The command runs on this repository.
- **THEN** The output names `tests/roadmap/test_roadmap_dry_runs.py`, `tests/roadmap/test_roadmap_limit_classes.py`, `tests/support/fakes/roadmap_store.py` and `tests/telemetry/test_telemetry_instruments.py`, each with a `path:line`.

### Requirement: A valid audit exits 0 and prints the count
The command SHALL exit 0 and print the count of valid declarations when each declaration is a plain literal and no ratchet assertion of a test module lacks a declared entry.

#### Scenario: All declarations valid
- **WHEN** Every declaration is a plain literal and no ratchet assertion lacks a declared entry.
- **THEN** The command prints the count of valid declarations and exits 0.

### Requirement: The audit reports a length ratchet with no declaration
The command SHALL report a `len(<name>) == <int>` assertion on an upper-case constant name or a module-level table of a test module, with its `path:line`, and SHALL exit 1, when no `REGISTRY_COUNTS` entry of that module covers `<name>`.

#### Scenario: A length assertion on a module table with no declaration
- **WHEN** A test module defines `TABLE = ("a", "b", "c")` at module level, asserts `len(TABLE) == 3` and holds no entry for `TABLE`.
- **THEN** The output holds a warning with the `path:line` of the assertion and the command exits 1.

### Requirement: The audit reports a limit tuple with no declaration
The command SHALL report a comparison of a tuple of upper-case constant names with a tuple of plain integers in a test module, with its `path:line`, and SHALL exit 1, when no `REGISTRY_COUNTS` entry of that module covers those names.

#### Scenario: A limit tuple with no declaration
- **WHEN** A test module asserts `(A, B, C, D) == (550, 75, 1100, 250)` and holds no entry for `A`.
- **THEN** The output holds a warning with the `path:line` of the assertion and the command exits 1.

### Requirement: The audit does not report a local length assertion
The command MUST NOT report `len(<name>) == <int>` when `<name>` is a local variable of a test function.

#### Scenario: A local list
- **WHEN** A test function assigns `rows = [1, 2, 3]` and asserts `len(rows) == 3`.
- **THEN** The output holds no warning for the assertion and the command exits 0.

### Requirement: The audit reports a declaration that is no plain literal
The command SHALL report a module-level `REGISTRY_COUNTS` declaration whose value is not a tuple or a list of literal triples, with its `path:line`, and SHALL exit 1.

#### Scenario: A computed declaration
- **WHEN** A test module sets `REGISTRY_COUNTS` to a call of a function.
- **THEN** The output holds an error with the `path:line` of the declaration and the command exits 1.

### Requirement: The audit emits JSON with --json
The command SHALL emit the same rows as JSON when it is given `--json` or `--format json`.

#### Scenario: The JSON format
- **WHEN** The command runs with `--json`.
- **THEN** The output parses as JSON and holds one object for each entry with the token, the kind, the target path and the source `path:line`.

### Requirement: The command declares the no-external-request dry-run class
The `registries` subcommand of the `roadmap` group SHALL declare the `no-external-request` dry-run class and MUST NOT add a `--dry-run` option.

#### Scenario: The dry-run ratchet
- **WHEN** The subcommand is registered in the `roadmap` group.
- **THEN** The dry-run class ratchet reports no unclassified command and `get_dry_run_class` returns `no-external-request` for it.

### Requirement: The generated documents name the command
The change SHALL regenerate the generated command pages and `devops docs check` MUST pass.

#### Scenario: The regenerated pages
- **WHEN** The subcommand is added and `uv run devops docs generate` runs.
- **THEN** The generated command pages name the `registries` subcommand of the `roadmap` group and `uv run devops docs check` exits 0.

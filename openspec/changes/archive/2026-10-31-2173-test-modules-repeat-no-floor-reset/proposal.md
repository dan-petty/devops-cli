# Proposal

## Why

Issue #2173: Test modules repeat floor resets that autouse fixtures in `tests/conftest.py` already execute for every test. Fixtures named `project` and `tree` are defined repeatedly with different structures across test modules. Five test helper files test test infrastructure or conftest behavior rather than `src/`. PyYAML parsing in `tests/security/test_semgrep_registry.py` uses deep nesting of 100,000 brackets, which consumes unnecessary CPU time.

## What Changes

- Remove redundant autouse fixtures repeating floor resets across test modules.
- Rename module-specific `project` and `tree` fixtures so each fixture name is defined once across `tests/`.
- Remove five test files that test test helpers or conftest rather than `src/`.
- Register the `test-settings` check spec and CLI subcommand in `devops ci` to verify pytest timeout configuration and conftest environment.
- Reduce YAML nesting in `tests/security/test_semgrep_registry.py` from 100,000 to 30,000 brackets.
- The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `tests/conftest.py` and multiple test modules under `tests/`
- `src/devops_cli/commands/ci.py` and `src/devops_cli/lang/en/messages.py`
- `tests/invariants/test_hermetic_floor.py`

## Feasibility

- AST inspection of test modules identified redundant autouse fixtures repeating conftest floor resets.
- PyYAML `CSafeLoader` C-stack overflow triggers at depth ~26,074. A depth of 30,000 brackets triggers the parser refusal without wasting runner time.
- Invariant tests in `tests/invariants/test_hermetic_floor.py` verify that duplicate floor resets, duplicate fixture names, and dead test files are absent.

## Existing Tool Considered

Pytest built-in fixture mechanics and Python standard library AST. No software tool is built.

# Tasks: #6419

## Group 1: Configuration and Schema Hook
- [x] 1.1 Add `osv-scanner.schema.json` enforcing `effectiveUntil`, `#N` reason, and forbidding `*` in `id`.
- [x] 1.2 Add `osv-scanner.toml` to the repository root.
- [x] 1.3 Add `check-jsonschema` hook in `.pre-commit-config.yaml` to validate `osv-scanner.toml`.
- [x] 1.4 Delete `.npm-audit-ignore.yaml`.

## Group 2: Core and Command Implementation
- [x] 2.1 Remove npm ignore loaders, filters, models, messages, and constants.
- [x] 2.2 Add `build_osv_audit_cmd` in `config/commands.py`.
- [x] 2.3 Add `_read_osv_failure` and register `BIN_OSV_SCANNER` in `_FAILURE_READERS` in `core/dependency_audit.py`.
- [x] 2.4 Update `ci.py` audit row to execute `osv-scanner` over the root `package-lock.json`.

## Group 3: Documentation and Verification
- [x] 3.1 Update `SECURITY.md`, `docs/ROUTINE_TASKS.md`, and `docs/SDLC.md` to reference `osv-scanner` and `osv-scanner.toml`.
- [x] 3.2 Update tests in `tests/commands/test_dependency_audit.py` and `tests/commands/test_ci.py`.
- [x] 3.3 Delete `tests/core/test_dependency_audit_ignores.py`.
- [x] 3.4 Verify OpenSpec validation and quality gates.

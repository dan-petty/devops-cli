# Tasks

## 1. The floor fails a test that writes under the real home

Kind: behavior. Changes: `tests/invariants/test_hermetic_floor.py`, `tests/support/bootstrap.py`, `tests/support/home_write_guard.py`, `tests/support/file_changes.py`, `tests/support/config_write_guard.py`, `tests/support/spend_write_guard.py`.

- [ ] 1.1 Write a failing test: in a pytester run whose real home is in the test's temporary directory, a test that opens a file for writing, opens a descriptor for writing, renames a file onto one or removes one under that home fails and is named, also when it catches the failure. A read under the home, and a write under `tmp_path`, under the isolated `HOME` and outside the home pass. No file under the home changes.
  - Verification: `$ uv run devops ci test tests/invariants/test_hermetic_floor.py`
- [ ] 1.2 Record the real home in `isolate_home` and give it to each xdist worker. Add the home write guard. Move the audit event table into `tests/support/file_changes.py` and read it in the three guards.
  - Verification: `$ uv run devops ci test tests/invariants/test_hermetic_floor.py tests/config/test_isolation_tripwire.py`

## 2. A support helper writes only inside a pytest run

Kind: behavior. Changes: `tests/invariants/test_hermetic_floor.py`, `tests/support/home_write_guard.py`, `tests/support/tools.py`, `tests/support/config.py`.

- [ ] 2.1 Write failing tests: `link_at_pin`, called from plain Python with `HOME` in the test's temporary directory, exits with the refusal and writes nothing. In a pytester run, `link_at_pin` with a user data root outside the run's temporary directory refuses and writes nothing.
  - Verification: `$ uv run devops ci test tests/invariants/test_hermetic_floor.py`
- [ ] 2.2 Add `hold_to_the_run`, and call it in `link_at_pin` for each path and in the write function of `global_config` before each write.
  - Verification: `$ uv run devops ci test tests/invariants/test_hermetic_floor.py tests/commands/test_install_tools.py tests/commands/test_devcontainer_install_tools_dry_run.py tests/config/test_setting_sources.py`

## 3. Documents

Kind: documents. Changes: `docs/TESTING.md`.

- [ ] 3.1 Name the home write guard and the rule for a support helper in the hermetic floor of `docs/TESTING.md`.
  - Verification: `$ uv run devops ci docs`

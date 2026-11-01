# Design

## Decisions

- **Remove the alias and keep the public name**: `_prepare_cmd` has no caller in `src/`. The project is before 1.0 and keeps no shim. `docs/TESTING.md` forbids a test to import a private name, so the fake and the test move to `prepare_tool_cmd`.
- **Lower the existing ceiling, and add no row**: the ratchet `src noqa: F401` already fails on a new site once its ceiling equals the count. The count is 0 on `main` (see the Feasibility section of the proposal). A new row would count the same sites with a second tool and would need a subcommand, a message, help text and documents (the `test-settings` row of #2173 changed the command, its message, `README.md` and two generated documents).
- **Show the failure by a probe file, not by a new test**: the ratchet already has a test. A new test that writes a file into `src/` would break `docs/TESTING.md`, which says a check of committed files is not a test that starts a program. Group 2 holds numbered steps that a person or an agent can repeat.

## Rejected alternatives

- **A `devops ci` row `ruff check --select F401 --ignore-noqa src` that counts findings against a ceiling of 14**: the 14 sites are gone (`ruff` reports 0), so a ceiling of 14 would let 14 new sites in. A row with a ceiling of 0 duplicates the ratchet at 0.
- **A `devops ci` row `ruff check --select F401 --ignore-noqa src` that fails on any finding, as an addition to the `lint` row**: it works, but it checks the same sites as the ratchet. The `lint` subcommand runs only the `cmd` of its row, so the check would run in `devops ci` and not in `devops ci lint`. If a person wants it, it is a follow-up change.
- **A pytest test that runs `ruff` and asserts on its output**: `docs/TESTING.md` says a test of `src/` starts no system program, and a check of committed files is a row of `devops ci`.
- **Keep the alias with a deprecation warning**: the alias has no production use, and the project keeps no shim before 1.0.

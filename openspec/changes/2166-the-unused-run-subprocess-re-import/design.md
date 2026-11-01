# Design

## Decisions

- **Use ruff check --select F401 --ignore-noqa as the check command**: ruff is already the project linter and the command is confirmed to report the 15 findings at b170358e. No new tool is needed.
- **Set the ceiling at 14**: This issue removes the 15th site (ruff.py:23), leaving 14 sites owned by #1332. The ceiling goes to zero when #1332 removes those sites.
- **Add the check as a devops ci row, not a pytest test**: docs/TESTING.md states: 'A check of committed files or of tool configuration is a row of devops ci, not a pytest test.'
- **Remove the alias rather than deprecate it**: The project is pre-1.0 and docs/TESTING.md forbids tests from importing private names. The alias exists only for a test fake, which is updated in the same change.

## Rejected alternatives

- **Add a pytest invariant test for the F401 ceiling**: docs/TESTING.md states: 'A check of committed files or of tool configuration is a row of devops ci, not a pytest test.'
- **Use a custom script to count noqa F401 imports**: ruff already reports these with --select F401 --ignore-noqa. A custom script adds tokens to build, keep and fix, and duplicates ruff's parser.
- **Keep the _prepare_cmd alias with a deprecation warning**: The project is pre-1.0. docs/TESTING.md forbids tests from importing private names. The alias has no production use.

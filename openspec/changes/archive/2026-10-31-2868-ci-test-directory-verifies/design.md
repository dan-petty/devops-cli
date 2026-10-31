# Design

## Overview

`_resolve_test_targets` in `src/devops_cli/commands/ci.py` normalizes the path arguments, maps them to test modules and returns the targets. A new step runs first and replaces each directory argument with the files it holds. The rest of the flow stays as it is.

## Directory expansion

For each normalized path that is a directory in the project root:

- At or under `tests/`: the test modules inside it, found with `rglob("test_*.py")` and kept when `is_test_module` agrees. A helper module or a conftest in the directory is not added. A helper would pull in every test that imports it, and a conftest forces the full suite, so a directory argument would run far more than the directory holds.
- At or under `src/`: the `.py` files inside it. Each one maps as a source file does: the coverage index first, then the text selector. When no file maps, the existing fallback applies: the full suite, or the refusal under `--no-fallback`.
- Anywhere else (`docs/`, `.` and so on): refused. No rule maps such a directory to a test.
- A path that does not exist: refused with `MESSAGES.ci.path_not_found`, unless `forces_full_run` says the name is a trigger. A deleted `conftest.py` or `uv.lock` still forces the full run, as before, because a change to it can alter any test. A renamed or mistyped directory is the case that the issue calls a silent pass: `devops ci test tests/invariantz` must not exit 0. The commit hook runs no tests (#2086), so no hook passes a deleted file; the changed-test job of `ci.yml` lists files with `--diff-filter=AMR`.
- A directory that gives no module (an empty directory, or one without a test module under `tests/`): refused.

A refusal prints `MESSAGES.ci.directory_without_tests` with the directory and exits 1 before any pytest starts. The message names the argument, as the issue asks.

Expanded paths replace the directory in the set of user paths, so the trigger check, the report of the selection and the worker count see test modules, as for a list of files.

## Rejected alternatives

- Exit non-zero for every directory. The issue allows it, but the plan-only step of `ci.yml` would still need a second command, and the user would list every file by hand. Rejected for the cost to the caller.
- Hand the directory to pytest as one target. `_narrowed_workers` counts one target and runs serially: 72 s for `tests/invariants` with `-n 0`. The count of modules and `--repeat` also need the files. Rejected on that evidence.
- Make every "nothing to verify" exit non-zero. The commit hook passes staged files such as `README.md`, and `test_cli_exits_cleanly_for_documentation_only_changes` requires exit 0. Rejected: a file that maps to no test is a fact about the file, not a skipped argument.
- Read pytest exit status 5. `_run` already treats any non-zero status as a failure. The gap is before pytest starts, so a change there does nothing.

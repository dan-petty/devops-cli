# Proposal

## Why

Issue #1729: `_bootstrap_managed_tools` in `src/devops_cli/commands/devcontainer.py` returned early when the variable `DEVOPS_CLI_SKIP_TOOL_BOOTSTRAP` was `1`, `true` or `yes`. Only tests set it: the autouse `isolate_devcontainer_env` fixture of `tests/test_devcontainer.py`, and one unit-test case. `docs/TESTING.md` says that product code holds nothing for tests, and AGENTS.md rule 2 says that product code does not detect tests.

## What Changes

- The variable check in `_bootstrap_managed_tools` is deleted. The `skip` parameter, which the public `--skip-tools` option of `devops devcontainer post-create` sets, stays the one way to skip the managed-tool bootstrap.
- The autouse fixture no longer sets the variable, and the unit-test case of the variable is deleted.
- Each test that runs `post-create` and does not test the managed-tool bootstrap passes `--skip-tools`. Each test that calls `_run_post_create_lifecycle` passes `skip_tools=True`.
- `devops devcontainer run-lifecycle` has no `--skip-tools` option. Its two tests put every tool of the packaged lock at its pin in the test's `~/.local/bin`, as `devops install-tools` leaves it, so the bootstrap runs and finds nothing to install. The helper that does this, `link_at_pin`, moves from `tests/test_install_tools.py` to `tests/support/tools.py`, and both test files use it.
- The test of a Node tool with no npm keeps the real bootstrap, as before.
- No consumer sees a change: no documentation, image, workflow or devcontainer file set the variable. So the change has no spec delta.
- This change fits one pull request.

## Impact

- `src/devops_cli/commands/devcontainer.py`.
- `tests/test_devcontainer.py`, `tests/test_install_tools.py`, and the new `tests/support/tools.py`.

## Feasibility

- On origin/main (2026-10-29), `git grep DEVOPS_CLI_SKIP_TOOL_BOOTSTRAP` found the variable in `src/devops_cli/commands/devcontainer.py` (one read) and in `tests/test_devcontainer.py` (the fixture, one `delenv` and the unit-test case). No document, workflow, image or devcontainer file names it.
- `skip_tools` in `_run_post_create_lifecycle` reaches only `_bootstrap_managed_tools(..., skip=skip_tools)`, so `--skip-tools` skips the same step that the variable skipped.
- A probe that recorded each test reaching the bootstrap, with the variable check gone, named 15 tests in `tests/test_devcontainer.py`. 13 of them hit the test floor's network refusal ("network edge reached without a fake"). Two reach it on purpose: the test of a Node tool with no npm, and `test_bootstrap_managed_tools`. `tests/test_instruction_generator.py` already passes `--skip-tools` or `--dry-run`.
- `_off_pin` in `src/devops_cli/commands/install_tools.py` decides that a tool is missing when its command in the target directory does not link to its locked version under the user data root. The test floor puts that root in the test's temporary directory, so links made there answer the check with no download.
- No open item owns this switch. #1325 restructures `tests/test_devcontainer.py` but does not name it, and #2512 listed the other test accommodations in `src/` with their owners. No source check is added: the bans of test switches in `src/` belong to #1336.

## Existing Tool Considered

None is needed. The change deletes a variable check and moves the tests onto the public `--skip-tools` option and the filesystem state that `devops install-tools` leaves. It builds nothing.

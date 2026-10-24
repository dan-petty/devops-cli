# Proposal

## Why

Issue #2086 shows that a commit in devops-cli waits minutes for the pre-commit hook `devops-ci-test-changed`, which runs `uv run devops ci test` on the staged Python files. The other pre-commit hooks take less than 1 second each. The pre-push gate (`uv run devops ci`) runs the full suite again, and CI runs it a third time. The owner decided on 2026-10-24 to remove the hook.

## What Changes

- Remove the hook `devops-ci-test-changed` from `.pre-commit-config.yaml`. A commit runs only the fast hooks: pre-commit-hooks, ruff, the AST structural invariants, ast-grep and the openspec gate.
- The pre-push gate and CI still run the full suite before code gets to GitHub, so no threshold changes.
- Add a test that fails when a pre-commit-stage hook runs the test suite.
- Remove the hook from the pre-commit diagram and list in `docs/SDLC.md`, and add the hooks that the list did not name.
- Change the module docstring of `src/devops_cli/core/test_selection.py`, which said that pre-commit uses the selector.
- `devops ci test <paths>` does not change, and its help text stays correct. The change alters a development hook and documents only, so it has no spec delta and sets `skip_specs: true`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `.pre-commit-config.yaml`: the hook is removed, and a comment on the pre-push hook gives the reason.
- `docs/SDLC.md`: the pre-commit diagram and list.
- `src/devops_cli/core/test_selection.py`: the module docstring.
- `tests/test_workflow_contracts.py`: the new test.

## Feasibility

Measured on 2026-10-24, on a host with 16 CPUs:

- `uv run pre-commit run --verbose --files <the 26 files of the #2031 commit>`: each hook before `devops-ci-test-changed` took 0.16 to 0.74 s. The covering-tests hook ran for more than 10 minutes under that day's load (load average 65 to 106 from parallel test suites), and then the run was stopped.
- `load_index(resolve_coverage_index_path(root))` gives an empty index: only `devops ci coverage --build-index` builds one, and no hook or workflow runs it. So the hook uses the text-based selector.
- `select_tests_for_sources` picks 109 of the 484 test modules for `src/devops_cli/config/constants.py`, 76 for `src/devops_cli/config/defaults.py`, and 0 for `src/devops_cli/lang/en/help.py`. When no staged source maps to a test, the hook runs the full suite.
- The pre-push hook `devops-ci-pre-push` runs `uv run devops ci`, which holds the `test` check over the full suite.

## Existing Tool Considered

pre-commit is the open tool, and its documentation recommends fast hooks at commit time. The tests stay in the pre-push gate and in CI. This change deletes a hook and builds nothing.

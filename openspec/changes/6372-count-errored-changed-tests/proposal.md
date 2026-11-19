# Proposal: #6372

## Why

The `Fail-to-Pass Check` failed 38 times from 2026-11-12 to 2026-11-19. In 22 of these runs, each
changed test errored on the base: an `ImportError`, `ModuleNotFoundError` or `AttributeError` at
collection or setup, because the base does not have the function, module or field that the fix
adds. On the head these tests pass. `devops ci fail-to-pass` counts only a failure in the call
phase, so a fix whose test must import new code cannot pass the check (#6372). The replay puts
the tests of the head on the base tree, so an error of a changed test on the base comes from the
code that the fix changes. SWE-bench also counts a test that fails or errors before the fix and
passes after it as FAIL_TO_PASS. Closes #6372.

## What Changes

- A changed test that errors on the base (at collection, import, setup or teardown) proves the fix,
  as a changed test that fails in the call phase does.
- pytest reports a collection error of a file as one case with no class name and the module path
  of the file as its name. This case names the whole file. It counts as changed when the syntax
  tree of the file differs from the merge base, or when the file is new.
- An error of a test that the fix does not change now refuses the replay, as a failure of such a
  test does. The replay on the plain merge base and on the head can still repair it.
- The report names each changed test that proves the fix on a line after its summary. The
  messages and the dry-run conditions say "fails or errors" where they said "fails".
- A replay that could not run, the host path guard rule (#3124) and the gate check path do not
  change.
- The command, its messages and its dry run change, so the change has a spec delta.

## Capabilities

### Modified

- `ci-fail-to-pass`: a changed test that errors on the base proves the fix, and an unchanged test
  that errors on the base refuses the replay.

## Impact

A fix whose test imports new code passes the check without a second test that fails in the call
phase. A fix that changes no test file still fails the check. The related #5585 covers the fixes
that change a pin or data in a `.py` file; this change does not close it. The change fits one pull
request.

## Feasibility

Confirmed against the code and against pytest 9.2.0. `FailToPassReport.satisfied` in
`src/devops_cli/ci/fail_to_pass.py` counts only outcomes with the status `failed`, and
`_unchanged_failures` reads only that status. A probe run of
`pytest -o addopts= -p no:cacheprovider --continue-on-collection-errors --junitxml=out.xml` on a
file that imports a missing module and on a test whose fixture reads a missing attribute wrote
`<testcase classname="" name="tests.test_collect">` with `<error message="collection failure">`,
and `<testcase classname="tests.test_setup" name="test_uses">` with
`<error message="failed on setup with ...">`. So a collection error has no test of its own, and
`_test_location` must map the module path in its name to the changed test file. The issue names
the census of the 38 runs and the three example runs.

## Existing Tool Considered

pytest's own `--junitxml` report already gives the status of each case, and the replay reads it.
No open tool decides which tests of a pull request are changed and which errors prove a fix: the
SWE-bench harness defines FAIL_TO_PASS the same way, but it runs a fixed task set in containers,
and does not read a diff of this repository. The change edits the existing rule in
`src/devops_cli/ci/fail_to_pass.py` and `src/devops_cli/ci/changed_tests.py`. It costs about 6,000
tokens to build, 1,000 tokens to keep, and about one hour. It deletes the property
`changed_failed_count`, which the new property `proof` replaces.

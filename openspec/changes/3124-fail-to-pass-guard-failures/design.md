# Design

## Decisions

- **Move the host path rules from `tests/conftest.py` to `tests/support/host_paths.py`.**: No test module may import a conftest, so a test could not hold the roots to a rule. The module holds pure functions with no fixture, and the conftest imports it when it installs the guard.
- **Add the common git directory of a linked worktree to the allowed roots, read with `_linked_worktree_common_dir`.**: The helper reads the `.git` file and the `commondir` file and starts no process. It covers the `HEAD` file and every other file of the common git directory.
- **Remove the main worktree path from the roots in this change.**: The replay of a changed test file ran in the replay tree without the path, and the new root covers a worktree of the main checkout. The path was a second, wider root that hid a missing root.
- **Treat the phrase `reached without a fake` as the mark of a guard failure.**: Every guard of the harness writes it, so one constant covers the host path, network edge, process edge and keyring edge. A guard failure is a harness failure and not a result of the fix.
- **Count a guard message in a failed test and in an errored test.**: The teardown error holds the guard message of a test that failed in its call phase, as the log of the issue shows.
- **Compare the syntax tree of each failed test function between the replay tree and the merge base.**: The replay tree holds the head tests, and `read_file_at_revision` gives the base text. `ast.dump` leaves out layout and comments, so only a change of statements counts. A test that is new, or that a source does not show or does not parse, counts as changed, so the gate refuses only a test that it knows to be unchanged. A change to the rest of the file (an import, a helper or a fixture) makes every test of the file changed, since an unchanged test then runs other code and can fail on the base for a reason that the fix adds. The first run of the gate on this change showed it: a changed report helper made seven unchanged tests fail on the base.
- **Compare only the failed tests.**: A passing unchanged test needs no comparison, and an errored test is a collection or fixture error that the report already counts apart.

## Rejected alternatives

- **Allow only `.git/worktrees/*/HEAD` by pattern.**: A pattern is too narrow. Other reads in the common git directory fail the same way.
- **Fake the `HEAD` read in the harness.**: The read is real and legitimate, and a fake needs the exact content of the file.
- **Remove the `HEAD` read from the tracer.**: The branch and revision are telemetry data, and the read starts no process.
- **Refuse a replay in which every test fails.**: A fix that adds one new test fails in full on the base and is valid. The `one new test` scenario of the spec holds that case.
- **Refuse any failure of an unchanged file.**: A changed file can hold an unchanged test that fails for a real defect of the base. The rule names the test.
- **Take the changed tests from the lines of `git diff`.**: A line range maps to a function only through a parse of both sources, so the comparison of the two parses is the same work with fewer cases.
- **Keep the main worktree path until a person confirms both forms.**: The replay without the path is the evidence for both forms, since the path was needed only for a worktree outside the checked-out tree.

## Known limit

The gate reads the changed test files only. A change to a shared file such as `tests/conftest.py` or a module of `tests/support/` can make an unchanged test of a changed file fail on the base, and the gate refuses that replay. The author moves that change to a pull request that is not a fix.

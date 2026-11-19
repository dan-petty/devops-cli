# Design

## Decisions

- The rule extends the existing no-proof path of #6207. It adds no escape line, label or flag: the
  replay reads no title, label or body (#1879), and a check that does not apply does not run.
- A new function in `src/devops_cli/ci/changed_tests.py`, the module of the syntax-tree rules,
  takes the base and the head source of one check module and gives the names of its deleted
  checks. It gives an empty tuple when the module does not only lose checks. The function:
  1. Parses each side with `ast.parse`. A side that is missing or does not parse gives an empty
     tuple. So a new module and a renamed module (git gives its new path, which the base does not
     hold) keep the replay.
  2. Leaves out the module docstring, and compares the top-level statements by `ast.dump`, which
     holds no line numbers. A comment, a blank line and a changed docstring change nothing.
  3. Asks that the head statements are the base statements in the same order with some left out
     (an ordered subsequence). An added, changed or moved statement gives an empty tuple.
  4. Asks that each left-out statement is an import (not `from __future__`), an assignment whose
     targets are plain names, a function or a class. Any other left-out statement, such as a
     top-level call or an `if` block, gives an empty tuple.
  5. Asks that the head uses no name that a left-out statement binds: no `ast.Name` node and no
     top-level function, class or import of the head has that name.
  6. Asks that at least one left-out statement is a `def check_*`. It gives the names of these
     checks in the order of the base, as `<module>.<check>`, where `<module>` is the file stem.
     The gate runner names a case in the same form.
- `changed_tests` in `src/devops_cli/ci/fail_to_pass.py` reads the base of each changed check
  module with `read_file_at_revision(root, merge_base, path)`. It reads the head from the working
  tree when the head is `HEAD`, as `materialise_base_with_head_tests` overlays it, and with
  `read_file_at_revision(root, head, path)` for a named head. `ChangedTests` gets the field
  `deleted_checks`, and `gate_checks` keeps only the modules that do not only lose checks.
- `run_fail_to_pass` keeps its first rule: no source file and no gate check left means no proof.
  The report gets the field `deleted_gate_checks`. When it is set and no proof is needed,
  `format_fail_to_pass_report` prints a new message, `fail_to_pass_deleted_checks` in
  `src/devops_cli/lang/en/messages.py`, that names each deleted check. Otherwise the old
  `fail_to_pass_no_source` message stays.
- A module that only loses checks starts no gate row. When another module of its row changes, the
  row still runs, and the kept cases of that module are unchanged cases: a base failure of one
  refuses the replay, as for any check module that the fix does not change.
- A deleted check module stays out of the replay. `changed_tests` lists no deleted path since
  #4554. The module has no case on the head, so no case of it can prove a fix. A module of the same
  row that imports from it fails to import on the head, and the gate row of the pull request
  reports that.

## Rejected alternatives

- Compare the statements as a multiset (any order). A move of kept statements can rebind a name,
  for example when two assignments give one name, and so change a kept case with no added
  statement. An ordered subsequence keeps each binding in its place.
- Accept any left-out statement. A left-out second assignment of a name that a kept check reads,
  or a left-out top-level call that sets state, changes a kept case. So a left-out statement must
  bind only names that the head does not use, and must be an import, an assignment, a function or
  a class.
- Compare only the names of the checks. A changed body of a kept check, or a changed helper, would
  then pass with no proof.
- Read only the `-` lines of `git diff`. A deleted line inside a kept check changes that check, and
  a text diff cannot tell it from a deleted check.
- Run the deleted check of the base on the base tree. It passes there, because the base holds the
  rule that it asserts, so it cannot show a fail-to-pass either.
- Add a label, a body line or a flag such as `--allow-deleted-checks`. The replay reads no title,
  label or body (#1879), and an escape line lets a fix pass with no proof.

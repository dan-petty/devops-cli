# Design

## Decisions

- One set of statuses, `failed` and `errored`, means "does not pass on base". The proof, the
  search for unchanged tests and the host path guard all read this set.
- `TestCaseOutcome.proves_fix` is true for a failure, and for an error whose message starts with
  pytest's `collection failure` or `failed on setup with`. `FailToPassReport.proof` lists the test
  IDs of the outcomes that prove the fix and are not unchanged and not repaired. `satisfied` asks for a proof or a gate case. The rule that a failure in no
  changed file counts as changed stays, and applies to errors too.
- A collection error of a file names no test. `_test_location` maps an outcome with no class name
  and the module path of a changed test file as its name to that file and an empty test name.
  `is_file_changed` in `changed_tests.py` decides for the whole file: the file is changed when its
  two parses differ, or when a parse is missing (a new file, or a file that does not parse). So a
  change of a comment alone does not make an errored file a proof, as it makes no test changed
  (#3124).
- The report prints the proof on one line after the summary, only when the replay is satisfied
  and the tests give a proof. A replay that the tests refuse prints its reason and no proof line.

## Rejected alternatives

- Count every error of a changed test as a proof: pytest also reports an error at teardown as an
  error, and gives a test whose call phase passes and whose fixture teardown errors one case with
  `failed on teardown with`. That test ran its assertions on base and they passed, so it does not
  show a fail-to-pass. The issue asks only for errors at collection, import or setup.

- Count every changed test file that errors at collection as a proof: a file whose head changes
  only a comment has the same syntax tree as the base, and the rule of #3124 counts no such test
  as changed. An error there does not come from the tests of the fix.
- Keep errors of unchanged tests out of the refusal: then a changed test that errors and an
  unchanged test that errors on base for another cause would satisfy the replay. The issue asks
  that an error of a test that the fix does not change fails the replay.
- Give back the `Fail-to-pass: not applicable` line of #844: the replay reads no title, label or
  body (#1879), and an escape line lets a fix pass with no proof.
- Change the proof rule of the implement step (`judge_replay` in
  `src/devops_cli/roadmap/implement/implement_base_replay.py`) too: that gate gives a repair round
  to a group whose tests error on base, and the issue names only the check of the pull request.

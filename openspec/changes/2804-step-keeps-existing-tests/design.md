# Design

## Decisions

- **The rule is by qualified name.** A test is `test_x` or `Class.test_x`, with the names of nested classes joined by dots. A rename is a loss. A change of the body is not. The issue asks for the rule by name, and a name is the one fact that a parser gives with no guess.
- **Which defs count.** A function or an async function whose name starts with `test_`. The walk goes into classes, and into the blocks of `if`, `try`, `with`, `for`, `while` and `match`, so a test that a platform check guards is kept as well. The walk stops at a function: a `def test_x` inside a function is a helper of that test. Decorators do not matter, so a parametrized test is one function and its cases are not names.
- **Which files count.** A path under `tests/` that ends with `.py`, listed by git as changed, between the start commit and the checkout. A file that the step did not touch cannot lose a test. A new file has no tests to lose. A file that is not Python is not parsed.
- **A deleted file loses all its tests, unless they moved.** The check lists the changes with `--no-renames`, so a move is a delete plus an add, whatever the git settings are. A lost name is excused by one name that is new in a changed test file: new means that the name is in the file after the run and was not in that file at the start. Each new name excuses one lost name, in the order of the sorted paths. A step that moves a test and keeps a copy in the old file is not a loss either way.
- **A syntax error is skipped, and not reported.** At the start, a file that does not parse gives no list, so the file keeps no test from the check. After the run, `ruff check` reports the error, and the repair turn can fix it. A second reason for the same file would be a double report. A file that does not parse after the run adds no new names, so it excuses no loss. A bad parse does not hide a loss in another file.
- **The check runs second.** It runs after the head check and the restore of `tasks.md`, and after the no-change check, because it needs the staged tree. It runs before the formatter and the verification commands. A verification command can run the whole test file for minutes, and the step discards the work anyway. The reason is also the most useful one: it names the tests, and not a symptom of their loss. The formatter does not change names. A repair turn runs the exit checks again from the start, so a repair turn cannot remove a test and pass.
- **No extra turn.** A lost test is a loss of work the agent chose, and a rewrite is the fix, not a one-line edit. The step stops, as the issue asks, and the diff in the stop comment shows the work. A person who wants to remove a test does it in a pull request of their own.
- **The reason is bounded.** It names the file and at most `CONST_ROADMAP_IMPLEMENT_REASON_TESTS` functions, then the count of the rest. It names at most `CONST_ROADMAP_IMPLEMENT_REASON_PATHS` files with the same count rule. The stop comment cuts a reason to `CONST_ROADMAP_IMPLEMENT_REASON_CHARS` characters in any case.
- **Pure functions in a module of their own.** `implement_step.py` is 1,300 lines. The module `implement_test_names.py` holds `test_names(text)` and `lost_tests(before, after)`, with no I/O. `implement_step.py` reads git and formats the reason.

## Rejected alternatives

- **`pytest --collect-only` before and after.** It imports the modules and runs their top-level code, and it needs a second checkout at the start commit. A file with an import error gives no list. Rejected for cost and risk, see the proposal.
- **Compare the count of tests.** A step that deletes one test and adds one passes. The issue asks for names.
- **Use the rename detection of git.** `git diff -M` pairs a deleted file with an added file by a similarity guess. A step that replaces a file with a small new file is not a rename, and a threshold would decide the result. A name comparison needs no threshold.
- **A regular expression for `def test_`.** The issue forbids it, and it cannot tell a method from a function, or a def in a string.
- **Give the agent an extra turn to restore the tests.** The restore is a rewrite of work the agent chose to drop, and the issue asks for a stop. A person decides about a removal.
- **Check every test file in the repository.** A file that the step did not change cannot lose a test, and the check would depend on the whole tree.
- **Skip the check when the group names the file.** A group that names a test file asks for tests to be added. It never asks for a removal. The merged pull request had such a group.

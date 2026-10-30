# Proposal

## Why

Issue #2804. The implement job made a pull request for #2745. In it, the agent replaced the whole of `tests/test_config_write_history.py` with two new tests. The file had seven tests at the start of the step. The step passed all its checks and the pull request was merged, because a deleted test cannot fail.

The step judges the work with the verification commands of the group, `ruff check` and `mypy --strict`. Nothing checks that the step keeps the tests that existed before it. A step may add tests. It may not remove one.

## What Changes

- A new exit check lists, for each test file that the step changed and that existed at the start commit, the test functions of the file at the start. When one of them is not in the file after the run, the step stops. The reason names the file and the missing functions, up to a fixed number of them.
- A test file is a Python file under `tests/`. A test function is a function or an async function whose name starts with `test_`, at module level or in a class, also inside an `if`, `try` or `with` block. A function is named by its qualified name: `test_x` or `Class.test_x`. A parametrized test is one function. A function inside another function is not a test.
- A step that deletes a test file loses all its tests. A step that moves a test from one file to another loses it: every test stays in its file, and a person moves tests in a pull request of their own. A step that renames a test loses the test: the rule is by name.
- A file with a syntax error is skipped. At the start, there is no list to compare. After the run, the static check judges the file, so the new check does not report it twice.
- The check runs second, after the check that `HEAD` did not move, and before the formatter and the verification commands. It is cheap, and the verification commands can run for minutes. The step discards the work in any case, so it must not spend that time first. The check gives no extra turn: a lost test is not a fault of style that one edit removes.
- The module `implement_test_names.py` holds the list of names and the comparison, in pure functions. `implement_step.py` holds only the git calls and the reason text.
- The instructions of the step tell the agent the rule.
- A consumer observes the exit order and a new reason, so the change carries a spec delta. It modifies one requirement of `roadmap-implement-step` and adds one.
- This change fits one pull request.

## Capabilities

### Modified Capabilities

- `roadmap-implement-step`: the order of the exit checks, and a new requirement for the check that keeps the existing tests.

## Impact

- `src/devops_cli/roadmap/implement_step.py`, a new `src/devops_cli/roadmap/implement_test_names.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/ai/tasks/roadmap_implement_step.md`.
- A new `tests/test_roadmap_implement_step_tests_kept.py`, and a new `tests/test_roadmap_implement_test_names.py`.
- The documents that `devops docs generate --sync-readme` writes.

## Feasibility

- The defect is real. In `git show 72b82e38 -- tests/test_config_write_history.py`, the file has 7 test functions at `72b82e38~1` and 2 at `72b82e38`. A walk of both versions with the standard library `ast` lists the 7 lost names, such as `test_the_first_write_of_a_config_file_records_its_keys_and_keeps_no_copy`. The same commit adds `tests/config/test_config_file_mode.py`, and none of the 7 names is in it. So a rule by qualified name stops this commit.
- No exit check looks at tests today. `_exit_failure` in `implement_step.py` runs, in order: the head check, `_restore_tasks`, the no-change check, `_format_failure`, `_verification_failure` and `_static_failure`. None reads a test name.
- `_stage` cannot list a deleted file. It runs `git diff --cached --name-only --diff-filter=ACMR`, and `D` is not in the filter. The new check lists its own paths. `git diff --cached --name-status --no-renames -z <start> -- tests` gives a delete plus an add for a move, in the same shape on every machine, whatever `diff.renames` says. Git 2.55.0 was run for this.
- The text at the start is `git show <start>:<path>`. The step already runs git through `_git_output`, and the start commit is in the tree of the checkout.
- `ast.parse` from the standard library gives the names, and raises `SyntaxError` for a file that does not parse. `ast.iter_child_nodes` walks into `if`, `try`, `with` and class bodies, and the walk can stop at a function. A rename in git needs a similarity guess, and the check needs none: it compares names.
- The rule for a moved test is the rule of the issue. Git shows a move as a delete plus an add when renames are off, and the delete loses the tests. No same-name test in another file excuses a loss: a file that pytest does not collect would hide it.

## Existing Tool Considered

The standard library `ast` lists the test names, and git lists the changed paths and the text at the start commit. `pytest --collect-only` was considered. It imports the test modules, so it runs the code of a file that the agent wrote, needs the dependencies of every module, and takes seconds for each file. It also needs the files at the start, in a second checkout. A parse of the text needs none of this. `pytest` also finds names that a plugin makes. The rule here needs the names that a person wrote.

The change builds about 50 lines of product code and the tests. Cost, estimated: 60k tokens of agent work to build it, small upkeep, and 1 hour of elapsed time. The change deletes no code.

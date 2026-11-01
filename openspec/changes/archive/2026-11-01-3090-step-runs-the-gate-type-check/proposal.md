# Proposal

## Why

Issue #3090: the implement step runs `mypy --strict` on every Python file that it changed, and the step stops when mypy reports an error. Mypy also reports the errors of the files that a checked file imports. A step that changes one test file stops on old errors that it did not cause. Live stops of 2026-11-01: #2116 (`tests/security/test_scanner_tool_executor.py`, `import-untyped`), #2491 (`tests/support/fakes/process.py:310`) and #2166 (`tests/core/test_process.py:570`).

Tracker #3027 asks for one rule: the runner runs the same checks as the gate and the devcontainer, from the same definitions. The type check is the first case. `devops ci` runs `mypy --python-version 3.14 --strict src` and no type check on `tests/`. The step must run that check, not a stricter one.

## What Changes

- One definition of the type check of the gate in `src/devops_cli/ci/typecheck.py`: the paths (`src`), the options (`--python-version`, `--strict`) and the command line. The row `typecheck` of `devops ci` and the step both build their command from it.
- The step runs `mypy` with the options of the gate on the changed Python files under the paths of the gate. It runs no type check on a test file. If no changed file is under those paths, the step runs no `mypy`.
- `ruff check` and `ruff format` stay on every changed Python file.
- The prompt of the step, the help text of `devops roadmap implement` and the generated documents say what the step type-checks.
- The change has a spec delta in `roadmap-implement-step`: the checks of a step are observable. The delta adds one requirement and modifies none.
- The change fits one pull request.

## Acceptance

- Criterion 1, a step that changes `tests/security/test_scanner_tool_executor.py` does not stop on mypy errors of that file: group 1 (the step passes no test file to `mypy`).
- Criterion 2, a step that changes a file under `src/` still stops on a new `mypy --strict` error in that file: group 1 (the existing repair test and a new test).
- Criterion 3, the step takes the file set from the gate's definition, and a test fails if the two differ: group 1 (one module builds both commands, and a drift test compares them).
- Criterion 4, the decision and its reason are in the proposal: the section Decision below.

## Decision

The step follows the rule of the gate, not a baseline of old errors. Reason: a baseline would be a second list of errors to keep in step with the code, and the gate does not have it. The gate type-checks `src` and nothing else. A test file is not a product module, so a type error in it does not stop a merge. The step must not stop on more than the merge stops on. A new type error in a file under `src/` stops the gate, so it stops the step too.

## Feasibility

All commands ran on 2026-11-01 on `origin/main` (0dbd0921), mypy 2.3.1, Python 3.14, in a worktree with `uv sync --locked`.

- The step runs mypy on every changed Python file. `git grep -n "BIN_MYPY" -- src/devops_cli/roadmap/implement_step.py` shows `_static_failure`, which runs `uv run mypy --strict -- <files>` with every file from `_python_files`.
- The gate checks `src` only. `get_check_specs` in `src/devops_cli/commands/ci.py` builds the row `typecheck` as `uv run mypy --python-version 3.14 --strict src`. `.pre-commit-config.yaml` has no mypy hook, and the pre-push hook runs `lint,format,actionlint,zizmor`. So the devcontainer has no type check of a test file either.
- The error counts of the issue reproduce. `MYPYPATH=src uv run mypy --strict tests` printed `Found 741 errors in 221 files (checked 857 source files)` (the issue says 739 in 220: the tree grew by two since). `uv run mypy --strict -- tests/security/test_scanner_tool_executor.py` printed `Found 48 errors in 8 files (checked 1 source file)`, with `import-untyped` and `misc` errors in `tests/support/fakes/model.py`, a file that the test imports.
- The stop comments match. The stop of #2116 names `tests/security/test_scanner_tool_executor.py:25: error: Skipping analyzing "devops_cli.security.base" ... [import-untyped]`. The stop of #2491 lists `tests/support/fakes/process.py:310` and `tests/support/fakes/github.py:248`, which the agent did not change. The stop of #2166 lists `tests/core/test_process.py:570`.
- Files under `src` do not carry the problem. `uv run mypy --python-version 3.14 --strict -- src/devops_cli/github/app_installation.py src/devops_cli/lang/en/errors.py src/devops_cli/core/process.py` printed `Success: no issues found in 3 source files`. These are the `src` files of the stops of #2491 and #2166.
- Nothing newer did this work. `git log origin/main -S"BIN_MYPY" -- src/devops_cli/roadmap/implement_step.py` lists one commit, the one that added the command (#2684), so the file set has never been limited. An open-issue search for "mypy" and "type check" finds only #3090.

## Existing Tool Considered

- `mypy` itself with the options of the gate: no new tool and no baseline file. The change adds no parser and no filter of mypy output.
- The file set uses `pathlib.PurePosixPath.is_relative_to` of the standard library. It does not parse a path by hand.
- The command line of the gate and the step are built from one function, so the project keeps no second copy of the options.
- Code removed: the literal `(BIN_MYPY, "--strict")` tool tuple in `_static_failure`, and the list of `--strict -- <all files>` in the tests, which now follow the gate.

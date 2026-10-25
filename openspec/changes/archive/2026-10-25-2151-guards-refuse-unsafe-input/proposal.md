# Proposal

## Why

Issue #2151: two security guards have no test that makes them refuse their input. A change that removes one of the guards passes the suite.

- `build_subprocess_env` in `src/devops_cli/core/process.py` refuses a caller override of `LD_PRELOAD`, `LD_LIBRARY_PATH`, `DYLD_INSERT_LIBRARIES`, `DYLD_LIBRARY_PATH`, `BASH_ENV` or `ENV`, and a key or a value that holds a null byte. No test sends one of these overrides.
- `find_repo_files` in `src/devops_cli/review/targets.py` raises `SecurityError` for a target outside the repository root. It gives no files for a symlinked target file, and it leaves out a candidate that is a symlink or whose real path is outside the root. No test calls `find_repo_files`.
- The second condition of the symlink check of a target file (`not target_resolved.is_relative_to(root)`) cannot be true, because the function already raised for that target.

## What Changes

- Add parametrized tests to `tests/test_subprocess_env_boundary.py`. Each of the six refused keys, in upper and in lower case, with isolation on and off, raises `SecurityError` with the message that names the key. A null byte in a key and in a value raises `SecurityError` with the message that names the key.
- Add `tests/review/test_review_targets_stay_inside_the_repository.py`. It builds a repository and a tree beside it under `tmp_path`, with real files and symlinks. A target outside the root raises `SecurityError`: a directory, a file, a path through `..`, a symlink to a file and a symlink to a directory. A symlinked target file gives `[]`. A directory target leaves out each symlink it holds, and each file that a pattern reaches through a symlinked directory.
- Delete the unreachable second condition of the symlink check of a target file.
- Delete the `try`/`except OSError, RuntimeError` around the real-path check of a candidate. On Python 3.14 a non-strict `Path.resolve()` raises no error for a missing path, a loop or a denied directory, so no public behavior reaches the `except`. docs/TESTING.md says that such a line is dead code and that it is deleted.
- The tests start no program, patch no `devops_cli` name and read no host state.
- This change alters no behavior that a consumer observes: it adds tests and deletes code that no input reaches. The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/review/targets.py`: `find_repo_files` and its candidate filter lose the two checks that no input reaches.
- `tests/test_subprocess_env_boundary.py`: the refusal tests of `build_subprocess_env`.
- `tests/review/test_review_targets_stay_inside_the_repository.py`: the refusal and skip tests of `find_repo_files`.

## Feasibility

- Code inspection at base `527558fa`: the refused keys and the null-byte check are at `src/devops_cli/core/process.py:182-194`. The outside-root error is at `src/devops_cli/review/targets.py:79-80`, the candidate real-path check at `:50-54` and the symlink check of a target file at `:82-85`. `git grep -n find_repo_files origin/main -- tests` prints nothing.
- At line 83, `target_resolved` is the value that line 79 checked. Line 79 raises when `target_resolved` is not relative to the root, so the second condition of line 83 is always false.
- Python 3.14.7 runtime check: `Path.rglob("*/*.py")` follows a symlinked directory below the root, and gives `vendor/secret.py`, which is no symlink and whose real path is outside the root. The real-path check of a candidate is the only check that leaves it out. With the default pattern `*`, `rglob` gives the symlinked directory itself, and the symlink check leaves it out.
- Python 3.14.7 `posixpath.realpath` sets `ignored_error = OSError` when `strict` is false. A runtime check of `Path.resolve()` on a symlink loop and below a directory with mode `000` returned a path and raised nothing. Python 3.13 changed `resolve()` to raise no `RuntimeError` for a loop. `find_repo_files` resolves the target before it reads a candidate, so `os.getcwd()` raises there first for a relative target. No public behavior reaches the `except` of the candidate filter.
- The new tests pass on the base, because the guards are there. A scratch copy of the base with each guard removed in turn shows that a test fails for each guard:
  - The refused-key check removed: 24 failed. The check made case-sensitive: 12 failed.
  - The null-byte check removed: 4 failed. Only the key part removed: 2 failed. Only the value part removed: 2 failed.
  - The outside-root error removed: 5 failed.
  - The symlink check of a target file removed: 1 failed.
  - The symlink check of a candidate removed: 1 failed.
  - The real-path check of a candidate removed: 1 failed.

## Existing Tool Considered

pytest, with `pytest.mark.parametrize` and the `tmp_path` fixture, covers the need. The tests make real files and symlinks with `pathlib`. No new tool or library is necessary. The change deletes the unreachable condition in `find_repo_files` and the unreachable `except` in its candidate filter.

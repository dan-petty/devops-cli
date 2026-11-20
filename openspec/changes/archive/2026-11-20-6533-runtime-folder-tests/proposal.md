# Proposal: #6533

## Why

PR #6506 moved platformdirs from 4.14.7 to 4.14.8. Since then, two tests of `tests/core/test_process.py` fail on Service Image Tests shard 6: `test_a_link_below_the_runtime_folder_does_not_move_the_token_folder` and `test_the_root_of_the_file_system_as_the_current_folder_skips_no_candidate`. Closes #6533.

## What Changes

The two tests give the runtime folder through `platformdirs.user_runtime_path`, as `test_a_runtime_or_temp_folder_in_the_current_folder_gets_no_token_folder` already does. They no longer set `XDG_RUNTIME_DIR`. No code of `src/` changes.

## Capabilities

None. The behavior of `_runtime_folder` in `src/devops_cli/core/process.py` does not change.

## Impact

Service Image Tests shard 6 passes again on each pull request that runs it.

## Feasibility

- platformdirs 4.14.8, `platformdirs/unix.py`: `user_runtime_dir` "Accepts `$XDG_RUNTIME_DIR` only as a directory, not a symlink, that the user owns with mode `0700`, as the XDG spec requires, and only below parents no other user can replace." Else it gives its own fallback.
- The log of job 136415787802 (PR #6530, Service Image Tests shard 6): the token folder went to the parent of the test's runtime folder (`/tmp/pytest-of-devops/...`), the temp folder fallback, so platformdirs refused the runtime folder of the test.
- With the change, `pytest tests/core/test_process.py -k "runtime or root_of_the_file_system or token_folder"` gives 8 passed.

## Existing Tool Considered

pytest `monkeypatch` gives the folder. No new code.

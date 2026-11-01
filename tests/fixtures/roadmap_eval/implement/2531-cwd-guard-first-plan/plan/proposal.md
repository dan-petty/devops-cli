# Proposal

## Why

#2531 reports that a devops command run from a deleted working directory prints a FileNotFoundError traceback from _resolve_git_dir in the telemetry setup. The command does not report a clean error and does not complete. The root cause is that Path.cwd() raises FileNotFoundError when the directory no longer exists, and _resolve_git_dir does not catch it.

## What Changes

- Wrap the Path.cwd() call in _resolve_git_dir with a try/except OSError guard that returns None on failure.
- Add a test that patches Path.cwd to raise FileNotFoundError and asserts _resolve_git_dir returns None.
- Add a test that confirms _resolve_git_dir still returns the correct .git path for a valid working directory.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-telemetry`: Deleted CWD returns no git directory, Command completes without traceback from deleted CWD, Normal resolution unaffected

## Impact

- Code: `src/devops_cli/telemetry/tracer.py`
- Tests: `tests/test_tracer.py`

## Feasibility

- The code at src/devops_cli/telemetry/tracer.py line 628 shows current = (start_dir or Path.cwd()).resolve() with no exception handling around Path.cwd(). This confirms the premise of the issue.
- The same file already catches OSError in _resolve_git_dir_from_file (line 618) and _read_packed_refs (line 596), so catching OSError is the established pattern in this module.
- The caller _detect_vcs_metadata (line 646) already handles a None return from _resolve_git_dir by returning an empty dict, so returning None on a deleted CWD is consistent with the existing contract.
- First check: run uv run devops ci test tests/test_tracer.py to confirm the new test passes and existing tests are unaffected.
- Second check: run uv run devops ci test to confirm the full test suite passes with the guard in place.

## Existing Tool Considered

No external tool or library covers this need. The fix is a try/except OSError block of about 4 lines around the Path.cwd() call in _resolve_git_dir (src/devops_cli/telemetry/tracer.py:628). The written cost is one guard block, one test case, and the maintenance of that guard for the lifetime of the function. No internal code is deleted.

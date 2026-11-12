# Proposal: #4891

## Why

Issue #4891: `tests/invariants/test_hermetic_floor.py::test_a_support_helper_called_outside_pytest_writes_nothing` (added by #4857) fails in the `Service Image Tests` job (shard 5 of 6). The failure blocks the release pull request #4875 (0.115.0). The test starts its child process with `python -I`. `-I` ignores `PYTHONPATH`. The Service image test job finds pytest and the test dependencies only through `PYTHONPATH` (`.github/workflows/service-image-test.yml`, `PYTHONPATH="/opt/service-test/boot"`), so the child stops at `import pytest` with `ModuleNotFoundError`, and the guard message that the test expects does not come.

## What Changes

- The test starts its child with `-P -s` in place of `-I`. `-P` keeps the working directory off the import path, and `-s` drops the user site directory, as `-I` did. The child keeps `PYTHONPATH`, so it imports pytest and devops-cli where the test process does.
- No change to the guard, the helpers or the image.

## Feasibility

- `PYTHONPATH=<dir> python3 -I -c 'import sys; print("<dir>" in sys.path)'` prints `False`; with `-P -s` it prints `True`, and `''` is not in `sys.path` (Python 3.14.10).
- Reproduction of the image layout in the devcontainer: the base interpreter of the venv (`cpython-3.14.10`, no pytest) runs the test with `PYTHONPATH=<worktree>/src:<worktree>:<venv site-packages>`. On `origin/main` the test fails with `ModuleNotFoundError` in the child. With the change it passes.
- CI evidence: job 130899632355 of run 43132451416 (head e88b2c78 of #4875) shows the failure.

## Existing Tool Considered

- The CPython command line options (`-P`, `-s`, `-I`) cover the need. No code is added.
- Cost: about 40,000 tokens and 30 minutes to build; nothing to keep.

## Impact

- `tests/invariants/test_hermetic_floor.py` only. The change fits one pull request.

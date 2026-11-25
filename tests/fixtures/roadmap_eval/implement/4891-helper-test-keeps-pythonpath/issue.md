### What happened?

`tests/invariants/test_hermetic_floor.py::test_a_support_helper_called_outside_pytest_writes_nothing` (added by #4857) fails in the `Service Image Tests` job of `ci.yml` (shard 5 of 6, first seen on #4872):

```
assert 'no pytest run is active' in 'Traceback (most recent call last):
  File "<string>", line 4, in <module>
    from tests.support.tools import link_at_pin
  ...
  File ".../tests/support/home_write_guard.py", line 45, in <module>
    import pytest
ModuleNotFoundError: No module named 'pytest'
```

The test starts its child with `python -I`. In the Service image, pytest is not in `/app/.venv`: the job installs the dev packages into a mounted directory and adds it with `PYTHONPATH=/opt/service-test/boot` and a `sitecustomize`. `-I` ignores `PYTHONPATH`, so the child cannot import pytest and stops before the guard. In the devcontainer and in `Tests & Coverage`, pytest is in the venv, so the test passes there. #4857 changed no image content, so its pull request did not run the job.

### Expected behavior

The child process imports the same pytest as the test process, and the test passes in the Service image too.

### Steps to reproduce

1. Open a pull request that changes image content (for example `Dockerfile`), so that `Service Image Tests` runs.
2. Shard 5 of 6 fails on the test above.

### Proposed fix

Keep `-I`, and give the child the directory of the parent's pytest: pass `Path(pytest.__file__).parent.parent` as an argument and put it on `sys.path` in the child script, beside `REPO_ROOT`.


<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Agent", "Priority": "P2-Medium", "Status": "In Progress", "Value": "Medium", "intake.jev_shadow": "{\"at\":\"2026-11-12T02:09:16Z\",\"answers\":{\"priority\":[\"P1-High\",0.66,\"P2-Medium\"],\"value\":[\"Medium\",0.41,\"Medium\"],\"effort\":[\"Low\",0.94,\"Low\"],\"duplicate\":[\"\",0.06,\"\"]}}"} -->

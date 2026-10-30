# Spec Delta

## MODIFIED Requirements

### Requirement: A runner process cannot be read by its own shell
Before the first step, the job in a runner SHALL clear the dumpable flag of its own process with `prctl(PR_SET_DUMPABLE, 0)`. A child of the job SHALL then not read `/proc/<pid>/environ` of the job. A call that the kernel refuses SHALL make `apply_implement` raise `RoadmapImplementError`, and no step SHALL run. The step of the agent SHALL get none of the variables of the job, except the paths `UV_CACHE_DIR` and `UV_PYTHON` of uv and `PYTEST_XDIST_AUTO_NUM_WORKERS`, the worker bound of the test runner.

#### Scenario: A child reads the environment of its parent
- **WHEN** a process sets the flag, holds a variable in its starting environment, and starts a child that opens `/proc/<parent pid>/environ`
- **THEN** the child gets `PermissionError`

#### Scenario: The refusal
- **WHEN** `prctl` returns -1 and `apply_implement` runs a plan
- **THEN** `apply_implement` raises `RoadmapImplementError` that names `PR_SET_DUMPABLE`, and no step, no model request and no program runs

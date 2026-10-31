# Spec Delta

## ADDED Requirements

### Requirement: An isolated child gets the worker bound of the test runner
With isolation on, `build_subprocess_env` SHALL keep `PYTEST_XDIST_AUTO_NUM_WORKERS` in the child environment when the process has it. `pytest-xdist` counts the CPUs of the node, not of the pod, so a child that runs `pytest`, such as the gate of `devops ci`, needs the bound that the runner pod sets.

#### Scenario: The process has the variable
- **WHEN** the process sets `PYTEST_XDIST_AUTO_NUM_WORKERS` to `2` and a caller builds an isolated child environment
- **THEN** the child environment holds `PYTEST_XDIST_AUTO_NUM_WORKERS` with the value `2`

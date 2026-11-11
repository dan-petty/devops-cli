# Proposal: #4466

## Why
`test_bootstrap_k8s_warns_when_docker_daemon_down` takes 45 s on every run. `_wait_for_docker_daemon` reads `time.monotonic()` and calls `time.sleep(2)` directly. The `clock` fixture cannot answer `time.monotonic()`, so the loop runs as a CPU busy-spin for 45 real seconds. Closes #4466.

## What Changes
- `_wait_for_docker_daemon` reads and waits through `devops_cli.core.clock` (`monotonic`, `sleep`).
- The warning test asks for the `clock` fixture and asserts the recorded waits.
- A new test proves the 45 s default timeout on the fake clock.

## Capabilities
- k8s-bootstrap: adds the requirement "Docker daemon poll uses the clock seam".

## Impact
No change in production behavior: same 45 s timeout, same 2 s poll interval. The test takes under 1 s instead of 45 s. Only `src/devops_cli/commands/devcontainer.py` and `tests/commands/test_devcontainer.py` change.

## Feasibility
Checked on base: `uv run pytest tests/commands/test_devcontainer.py -k docker_daemon -n0` did not finish within 120 s with the new assertions, and the function body uses `time.monotonic()` and `time.sleep()` in `devcontainer.py`. With the change, the whole test file passes in 17 s and the slowest test takes 1.1 s.

## Existing Tool Considered
The project clock seam `devops_cli.core.clock` and the `ClockFake` fixture (backed by `time-machine`) already cover the need. No new code to keep.

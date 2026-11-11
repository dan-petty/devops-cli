## ADDED Requirements

### Requirement: Docker daemon poll uses the clock seam
`_wait_for_docker_daemon` SHALL measure elapsed time with `clock.monotonic()` and wait with `clock.sleep(2)` from `devops_cli.core.clock`, and SHALL keep its default timeout of 45 seconds.

#### Scenario: Unreachable Docker engine
- **WHEN** the Docker engine is unreachable and the poll runs with the default timeout under the fake clock
- **THEN** the function returns False and the clock records 23 waits of 2 seconds

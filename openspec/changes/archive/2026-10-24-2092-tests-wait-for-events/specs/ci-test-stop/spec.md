# Spec Delta

## Purpose

How `devops ci test` stops the pytest run that it starts in a session of its own when Ctrl-C, SIGTERM or SIGHUP comes, and why a second signal cannot leave the run's process group alive.

## ADDED Requirements

### Requirement: Each stop signal cancels the run
While `devops ci test` runs pytest on the main thread, Ctrl-C's SIGINT, SIGTERM and SIGHUP SHALL each cancel the run at once and raise no exception, also when the signal comes just before the run's event loop starts to wait or the kernel hands it to a thread other than the main one. A signal that the process ignores SHALL stay ignored. When the run ends, the handlers that were in place before it SHALL come back. A run that a stop signal cancels SHALL exit as cancelled, with exit status 130.

#### Scenario: The run takes over the stop signals and hands them back
- **WHEN** `devops ci test tests/test_x.py` runs, and its run ends or raises
- **THEN** while the child runs, the handlers of SIGINT, SIGTERM and SIGHUP are the run's own
- **AND** after the run, the handlers that were in place before it are back

#### Scenario: A SIGTERM that another thread takes
- **WHEN** a SIGTERM comes while the run's event loop waits for its child, and the kernel hands the signal to a thread other than the main one
- **THEN** the stop sends the run's group its SIGINT, and the child's teardown runs
- **AND** the run exits as cancelled, with exit status 130

#### Scenario: An ignored hangup stays ignored
- **WHEN** `devops ci test tests/test_x.py` runs under `nohup`, which ignores SIGHUP
- **THEN** SIGHUP stays ignored while the child runs, and the run takes over SIGINT and SIGTERM

### Requirement: A second stop signal cannot skip the SIGKILL
When a stop signal cancels the run, the stop SHALL send the run's process group SIGINT, then SIGTERM, each with its grace, then SIGKILL. A second stop signal SHALL cut the grace short and SHALL never skip the SIGKILL, also when its handler runs just after the stop sent the group its SIGINT.

#### Scenario: A second Ctrl-C just after the stop sends its SIGINT
- **WHEN** a first Ctrl-C cancels a run whose child and grandchild ignore SIGINT and SIGTERM, and the handler of a second Ctrl-C runs just after the child gets the stop's SIGINT
- **THEN** the SIGKILL stops the child and the grandchild
- **AND** the child gets no SIGTERM after the second Ctrl-C
- **AND** the run exits as cancelled, with exit status 130

#### Scenario: A second signal to a run that does not end
- **WHEN** a first Ctrl-C, SIGTERM or SIGHUP reaches `devops ci test`, and a second one of the same signal comes while the stop waits out its grace
- **THEN** the SIGKILL stops the run's child and grandchild, which ignore SIGINT and SIGTERM
- **AND** the child gets no SIGTERM after the second signal

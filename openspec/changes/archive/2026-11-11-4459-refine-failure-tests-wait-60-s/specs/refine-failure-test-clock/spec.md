## Purpose

The tests of the refine failure class wait on the fake clock, not on the real retry backoff of the model client, so that a failing refine round costs no wall time.

## ADDED Requirements

### Requirement: The failure-class tests use the shared fake clock
The test module of the refine failure class SHALL use the shared `ClockFake` fixture as its `clock`, and SHALL move that fake to `START` before each test. The module SHALL NOT define a fixture named `clock`.

#### Scenario: A test requests the clock
- **WHEN** a test in the failure-class module requests the `clock` fixture
- **THEN** it receives the shared `ClockFake`, whose wall clock reads `START` and whose `waits` list is empty

### Requirement: A failing round waits on the fake clock
A refine round that exhausts the gateway retries SHALL record each retry wait in `clock.waits` and SHALL NOT call the real `time.sleep`.

#### Scenario: A gateway timeout exhausts the retries
- **WHEN** a test scripts a gateway timeout for one item and runs one refine round
- **THEN** `clock.waits` is not empty after the round and the round returns at once

### Requirement: The timeout test guards the fake clock
The timeout test of the module SHALL assert that `clock.waits` is not empty after the failing round, so that a module fixture that shadows the shared `clock` makes the test fail.

#### Scenario: The module shadows the shared clock
- **WHEN** a module fixture named `clock` replaces the shared `ClockFake`
- **THEN** the timeout test fails

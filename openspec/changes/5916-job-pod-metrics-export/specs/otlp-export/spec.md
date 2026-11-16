## ADDED Requirements

### Requirement: A process that runs on exports its metrics at a fixed interval
The tracer SHALL export the metrics that it holds every `OTEL_METRIC_EXPORT_INTERVAL` milliseconds from the first metric of the process on, through the same flush as the end of a command. The interval SHALL be 60000 milliseconds when the variable is not set, or when its value is not a finite number of milliseconds above zero. Each export SHALL hold only the deltas since the export before it.

#### Scenario: A long command exports before it ends
- **WHEN** a command records tokens and runs on past the interval
- **THEN** the collector holds the tokens while the command still runs

#### Scenario: A periodic export and a round flush count each delta once
- **WHEN** the process records 3 tokens, exports at the interval, records 2 tokens and flushes after a round
- **THEN** the exported deltas add up to 5, and each point starts at or after the end of the point before it

#### Scenario: A short command exports once
- **WHEN** a command records tokens and ends before the first interval
- **THEN** the collector gets one metric export request, and no export thread runs after the shutdown

#### Scenario: A value that is not a number of milliseconds above zero
- **WHEN** `OTEL_METRIC_EXPORT_INTERVAL` is zero, negative, infinite or not a number
- **THEN** the interval is 60 seconds

### Requirement: SIGTERM exports the telemetry before the process stops
The `devops` entry point SHALL set a SIGTERM handler that exports what the tracer holds and then does what the handler before it did. The handler SHALL call a Python handler before it, keep an ignored signal ignored, and else set the default action and send SIGTERM to the process again.

#### Scenario: A Python handler before
- **WHEN** a process with a Python SIGTERM handler runs the `devops` entry point, records tokens and gets SIGTERM
- **THEN** the collector holds the tokens, and the handler before runs once

#### Scenario: The default action before
- **WHEN** a process with the default action for SIGTERM installs the handler, records tokens and gets SIGTERM
- **THEN** the process exports one metric request, and SIGTERM ends it

#### Scenario: Two installs keep one handler
- **WHEN** the handler is installed two times and uninstalled one time
- **THEN** the handler before the first install is in place

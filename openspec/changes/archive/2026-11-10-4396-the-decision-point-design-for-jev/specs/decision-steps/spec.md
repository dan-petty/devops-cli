## MODIFIED Requirements

### Requirement: A decision step runs in shadow before a switch
A decision step SHALL be a decision point, and the setting `roadmap.decisions` SHALL hold its mode, which is `off` unless a person sets it. A step in the mode `shadow` SHALL log and count its band beside the real result and SHALL change nothing else. The metric SHALL be the counter `devops_cli_decision_point_total`, whose labels have a bounded set of values, and the documents SHALL state its series count.

#### Scenario: Shadow changes nothing
- **WHEN** a decision step runs in shadow mode with a fake Jev
- **THEN** the real path runs as with the mode `off`, one log record and one counter increment name the band, and the result of the workflow is equal

### Requirement: A decision step fails open
A decision step SHALL send the case to the existing path when Jev raises an error, times out, leaves a question unanswered, answers with a confidence below the fitted floor, or when no decision model is configured. It SHALL log the cause, except when no decision model is configured. A Jev answer SHALL NOT be the only security control of any path.

#### Scenario: Jev fails
- **WHEN** a decision step gets an error from Jev
- **THEN** the existing path runs and one log record names the error

#### Scenario: No decision model is configured
- **WHEN** a decision step runs with `ai.decision_model` empty
- **THEN** the existing path runs and no request goes to Jev

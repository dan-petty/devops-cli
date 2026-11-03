## MODIFIED Requirements

### Requirement: A failed model call ends the step stopped
A run that ends on a failed model call (a `ModelAPIError` that is not a refused key) SHALL end as stopped, and the step SHALL reset the checkout. When the failure classification maps the failure to `change_tier` and the ladder for that step class has another tier available, the step SHALL advance to the next tier without incrementing the repair round counter. The outcome of a failed turn SHALL hold the requests and the tokens that the turn spent, the failed request included, and the last text of the model, added to those of the turn before it.

#### Scenario: A model call fails in the first turn
- **WHEN** the agent writes `src/sample.py` and a new test file, and its next model call raises a `ModelAPIError`, a `ModelHTTPError` with the status 503, or a `ModelRequestTimeout`
- **THEN** the step reports stopped with a reason that starts with the class of the error, the outcome holds the masked diff of both files, the requests (the reply and the failed request) and the tokens, and the last text of the model, and the checkout is reset

#### Scenario: A model call fails in the extra turn
- **WHEN** the first turn passes every check and leaves a task unticked, and the model call of the extra turn for the ticks raises one of those errors
- **THEN** the step reports stopped with a reason that starts with the class of the error, the outcome holds the masked diff of the work of the first turn, the requests of both turns, and the last text of the first turn, and the checkout is reset

#### Scenario: A parser failure advances to the next tier
- **WHEN** an attempt encounters an error classified as `change_tier` and another tier remains in the ladder
- **THEN** the next attempt runs on the next tier of the ladder and the repair round counter does not change

#### Scenario: Ladder tiers exhausted
- **WHEN** an attempt encounters an error classified as `change_tier` and no further tiers remain in the ladder
- **THEN** the step stops and resets the checkout

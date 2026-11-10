## Purpose
`decide_with_jev` in `src/devops_cli/ai/jev.py` is the one public way to send a request to a TypeSafe Jev model. One model serves any number of requests.

## ADDED Requirements

### Requirement: One model serves every request
`decide_with_jev` SHALL answer every request that it gets on one model, also when the HTTP client of the model keeps a connection from an earlier request. It SHALL build the Jev model from the settings when the caller gives no model.

#### Scenario: Two requests on one model over a real server
- **WHEN** a test sends two requests on one model to a keep-alive HTTP server on loopback
- **THEN** both requests return a response and none raises `RuntimeError`

#### Scenario: No model given
- **WHEN** a caller gives only the settings
- **THEN** the function builds the Jev model and returns the response

### Requirement: Errors reach the caller
`decide_with_jev` MUST raise to the caller the exception that `DecisionModel.decide` raises, with the same type, and a later call SHALL still run.

#### Scenario: A failing decide call
- **WHEN** `decide` of a model raises `ValueError`
- **THEN** `decide_with_jev` raises `ValueError`, and the next call on another model returns a response

### Requirement: The call settings win
`decide_with_jev` SHALL pass to `decide` the model settings merged with the settings of the call, and the settings of the call SHALL win.

#### Scenario: Call settings override model settings
- **WHEN** the model has `temperature` 0.1 and the call gives 0.7
- **THEN** `decide` receives 0.7 and keeps the other model settings

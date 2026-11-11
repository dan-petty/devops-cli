## MODIFIED Requirements

### Requirement: A Jev screen may skip the model review of a plan
The screen before the model review of a plan SHALL be the decision point `stage.verify_screen`, with its mode in `roadmap.decisions`. With the mode `on` and `ai.decision_model` set, the stage job SHALL ask the decision model nine yes/no questions about a digest of the input of the review in one request, and SHALL skip the review when no probability reaches its fitted cut. With any other mode or band, or with `ai.decision_model` empty, the review SHALL run.

#### Scenario: The setting is off
- **WHEN** the stage job reviews a plan and `stage.verify_screen` is not in `roadmap.decisions`
- **THEN** the reviewer runs and no request goes to the decision model

#### Scenario: No decision model is configured
- **WHEN** `stage.verify_screen` has the mode `on` and `ai.decision_model` is empty
- **THEN** the reviewer runs, no request goes to the decision model, and the counter `devops_cli_decision_point_total` has no series

#### Scenario: Mode on and the band continue
- **WHEN** the mode is `on` and every probability is under its cut
- **THEN** the reviewer is not called and the plan has no finding

#### Scenario: Mode on and a probability at its cut
- **WHEN** the mode is `on` and one probability is at or above its cut
- **THEN** the reviewer runs

#### Scenario: Mode shadow
- **WHEN** the mode is `shadow`
- **THEN** the reviewer runs, one counter point names the point, the resolver `model`, the band and the mode, and one decision record and one outcome record share an identifier and name the band and the result of the reviewer

### Requirement: The screen fails open
The screen SHALL run the review when the request to the decision model raises an error, times out or leaves a question unanswered, or when the digest holds a secret. It SHALL log the cause and count the resolver `fallback` with the band `none`.

#### Scenario: Jev fails
- **WHEN** the mode is `on` and the request to the decision model `typesafe/jev-1.14` fails with HTTP 503
- **THEN** the reviewer runs, one warning names the error, and the counter counts the resolver `fallback` with the band `none`

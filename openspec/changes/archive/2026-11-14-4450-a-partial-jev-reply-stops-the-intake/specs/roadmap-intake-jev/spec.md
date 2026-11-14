# roadmap-intake-jev Specification

## ADDED Requirements

### Requirement: Shadow duplicate check
The shadow duplicate check SHALL read the nearest item only through `best_neighbour` from `intake_jev.py`, and SHALL NOT hold a `duplicate_of_` literal or an answer guard of kind `object`.

#### Scenario: Shadow duplicate answer name
- **WHEN** A test reads `_duplicate` in `intake_jev_shadow.py`.
- **THEN** The function calls `best_neighbour`, holds no `duplicate_of_` literal, and holds no `_answer_of` call whose kind is `object`.

### Requirement: Shadow answer error
`observation_of` SHALL raise `ShadowError` when a choice or score answer is missing or has a wrong kind.

#### Scenario: Missing priority answer
- **WHEN** `observation_of` receives a response with no `priority` answer.
- **THEN** `observation_of` raises `ShadowError`.

### Requirement: Shadow docstring
The docstring of `observation_of` SHALL name `ShadowError` as the error of a missing or wrong-kind choice or score answer, and SHALL state that the decision model refuses a partial reply.

#### Scenario: Docstring names the error and the model check
- **WHEN** A test reads the docstring of `observation_of`.
- **THEN** The docstring names `ShadowError` and does not say that a missing duplicate answer raises it.

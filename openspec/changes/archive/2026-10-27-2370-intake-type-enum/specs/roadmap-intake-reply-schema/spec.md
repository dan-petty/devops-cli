## Purpose

The reply schema that `devops roadmap intake` sends with each proposal request, so that the structured output of the model keeps each field that has a fixed list of values to that list.

## ADDED Requirements

### Requirement: The proposal schema lists the values of each fixed field
The reply schema that intake sends for a proposal SHALL make `type` required and one of the request's `types`, `priority` one of `P1-High`, `P2-Medium` and `P3-Low`, and `value` and `effort` each one of `High`, `Medium` and `Low`, each list as an `enum`. When the request has no `types`, `type` SHALL stay free text.

#### Scenario: A request with types
- **WHEN** intake asks for a proposal with the types `type/bug` and `type/feature`
- **THEN** the schema it sends requires `type`, `priority`, `value` and `effort`, with the enums `["type/bug", "type/feature"]`, `["P1-High", "P2-Medium", "P3-Low"]`, `["High", "Medium", "Low"]` and `["High", "Medium", "Low"]`

#### Scenario: A reply with an empty type
- **WHEN** a reply to a request with types has an empty `type`
- **THEN** the schema of the request refuses the reply

#### Scenario: A request with no types
- **WHEN** intake asks for a proposal with no types
- **THEN** the schema it sends has `type` as a string with no enum

### Requirement: Intake asks the model once for each candidate
Intake SHALL send one proposal request for each candidate. When the proposal names a value that is not on its list, intake SHALL skip the candidate, write nothing for it, and name the problem in its report.

#### Scenario: A proposal with a type off the list
- **WHEN** the model proposes the type `type/perf`, which is not one of the repository's types
- **THEN** intake sent one proposal request, skips the candidate with "type 'type/perf' is not one of" in its reason and report, and places no item

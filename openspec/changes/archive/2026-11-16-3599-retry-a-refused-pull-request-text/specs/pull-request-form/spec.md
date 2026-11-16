## ADDED Requirements

### Requirement: A body text that ends with a cut mark is refused
`body_problems` and `plan_body_problems` SHALL name a problem when the text above `Closes` or `Plans` ends with `...` or `…`, and `build_body` SHALL raise `ValidationError` that names it. The rule SHALL read the text as given and SHALL cut nothing.

#### Scenario: A cut why
- **WHEN** a body is built with a why that ends with `...`
- **THEN** `body_problems` names the cut mark and `build_body` raises `ValidationError` with no body returned

#### Scenario: A cut mark inside a sentence
- **WHEN** the why holds `...` in the middle of a sentence
- **THEN** `body_problems` finds no problem for it, and the body is built

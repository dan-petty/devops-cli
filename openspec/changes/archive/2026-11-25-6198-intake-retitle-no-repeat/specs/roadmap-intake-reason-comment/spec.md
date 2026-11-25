## ADDED Requirements

### Requirement: No Related line for a number in the body
Intake SHALL omit any `Related: #N` line from the reason comment when the candidate body already cites `#N` through the shared `#N` reference parser, and SHALL post no comment when no lines remain.

#### Scenario: Body cites related issue number
- **WHEN** intake plans a candidate whose body holds `#6167` and the model names `6167` as related with no other reason lines
- **THEN** intake posts no reason comment on the issue

### Requirement: A Possible duplicate line always stays
Intake MUST keep every `Possible duplicate: #N` line in the reason comment even when the candidate body already cites `#N`.

#### Scenario: Body cites possible duplicate number
- **WHEN** intake plans a candidate whose body holds `#6167` and the model names `6167` as a possible duplicate
- **THEN** the posted reason comment holds `- Possible duplicate: #6167`

### Requirement: The Priority line drops the label value
The Priority line of the reason comment SHALL keep the priority reason and any P0 granted or refused text, and MUST NOT copy the `priority/*` label value (`P0-Critical`, `P1-High`, `P2-Medium`, `P3-Low`).

#### Scenario: P1 priority omits label value
- **WHEN** intake plans an issue with priority `P1-High` and reason `users wait.`
- **THEN** the posted comment line reads `- Priority: `users wait.`` with no `P1-High`

#### Scenario: P0 grant keeps reason and shows one P0
- **WHEN** intake grants P0 from confirmed evidence with a priority reason
- **THEN** the Priority line keeps the reason and granted text and contains `P0` once

### Requirement: Contract check of intake comment against body
The intake comment contract tests SHALL verify that no non-duplicate line of the reason comment repeats an `#N` issue number present in the candidate body.

#### Scenario: Contract check enforces no repeated body issue numbers
- **WHEN** the intake reason-comment contract test inspects each non-duplicate line of a posted comment
- **THEN** no referenced `#N` issue number appears in the candidate body

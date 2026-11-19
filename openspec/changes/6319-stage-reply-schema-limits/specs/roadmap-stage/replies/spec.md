## ADDED Requirements

### Requirement: A long plan body gets a shorter text from one model turn
The reply schema SHALL hold no maximum length on `pull_request_body`. When its text is longer than the room that the plan form leaves for it, the stage job SHALL ask the model once for a shorter text with `BodyReply` and the length and the room, and SHALL build the draft body from that text. The proposal SHALL keep the full text. A shorter text that the plan form refuses SHALL go back to the planner as a refused body.

#### Scenario: A body of 1200 characters is staged
- **WHEN** the reply holds a `pull_request_body` of 1200 characters and the model gives a shorter text of 300 characters
- **THEN** the item is staged, the draft body holds the shorter text and at most 1000 characters before its trailers, and the proposal holds the 1200 characters

#### Scenario: A body in its room gets no rewrite
- **WHEN** the reply holds a `pull_request_body` of 100 characters
- **THEN** the model gets one request, and the draft body holds the text

#### Scenario: A shorter text that is still too long goes back to the planner
- **WHEN** the first reply holds a `pull_request_body` of 1200 characters, the shorter text holds 1100 characters, and the second reply holds a body of 100 characters
- **THEN** the second plan request holds the problem of the long body, and the draft opens with the second body

### Requirement: A null optional text reads as its default
The reply schema of the stage job SHALL read `null` as the empty text for `security` of the proposal and for `kind` of a reference. A value of another type SHALL break the schema and go back to the model once with the name of its field.

#### Scenario: A null security is staged
- **WHEN** the reply holds `security: null`
- **THEN** the model gets one request, the item is staged, and the proposal holds an empty `security`

#### Scenario: A number as security goes back once
- **WHEN** the first reply holds `security: 123` and the second reply is valid
- **THEN** the model gets two requests, the second names `security`, and the item is staged

## ADDED Requirements

### Requirement: The plan body passes the plan form before the draft opens
The stage job SHALL build the body of the draft pull request with `build_plan_body` and SHALL NOT write a body that `plan_body_problems` refuses. A refused body SHALL go back to the model with the other problems of the reply, once, and a second refusal SHALL stop the item as a reply that fails its checks. A text with a closing keyword SHALL keep its own stop.

#### Scenario: The plan body passes
- **WHEN** the model gives a `pull_request_body` of 100 characters for issue 42
- **THEN** the draft pull request gets a body that `plan_body_problems` accepts

#### Scenario: A short body is returned once
- **WHEN** the first reply has a `pull_request_body` of 5 characters and the second reply has a text of 100 characters
- **THEN** the second request holds the problem of the short body, and the draft opens with the second body

#### Scenario: A second refusal stops the item
- **WHEN** both replies have a `pull_request_body` of 5 characters
- **THEN** the job stops the item, opens no draft pull request and pushes nothing

## ADDED Requirements

### Requirement: The return request of a plan run is measured against the tool-removal limit
A test SHALL build the return request of a plan run at a window of 65536 tokens, count its tokens as the run hook counts them, print the count with the limit of 49152 tokens, and assert that the request stays under the limit.

#### Scenario: A gate return with a long earlier plan
- **WHEN** the stage test builds the return request of a reply that the content gate refuses, and the earlier plan is longer than the room below the limit
- **THEN** the test prints the count and the limit, the request counts under 49152 tokens, and the planner offers `read_spec`

#### Scenario: A review repair with a long earlier plan
- **WHEN** the stage test builds the repair request of a review round, and the earlier plan is longer than the room below the limit
- **THEN** the test prints the count and the limit, the request counts under 49152 tokens, and the planner offers `read_spec`

### Requirement: The earlier plan is bounded only when the return request passes the limit
The stage job MUST bound `previous` in a return request when the full request passes the limit at which the run offers no tool, and MUST keep the full `previous` when it does not. The bound SHALL cut the texts of the earlier plan and keep its keys, its paths, the `problem` text and every tool of the planner.

#### Scenario: The full earlier plan fits
- **WHEN** the full earlier plan leaves the return request under the limit at which the run offers no tool
- **THEN** the request carries the earlier plan with every text unchanged

#### Scenario: The full earlier plan passes the limit
- **WHEN** the full earlier plan makes the return request pass the limit
- **THEN** the request carries the earlier plan with its texts cut, keeps `problem`, and its measured size stays under the limit

#### Scenario: The keys of the earlier plan stay
- **WHEN** the stage job cuts the texts of the earlier plan
- **THEN** every key of the earlier plan is in the request, with its paths and its summary

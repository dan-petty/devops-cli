## MODIFIED Requirements

### Requirement: A request of a stopped step is judged before the item stops
When a step stops and its last message holds a request (`roadmap-plan-amendment`), the job SHALL judge the request before it stops the item. It SHALL commit an applied amendment as `docs(spec): amend the plan of group <n> (#N)`, read `tasks.md` again, and run the same group again. It SHALL apply one amendment for each group. A plan that fails the check of the selection is left out before the run, so no request amends a missing test path or a refused command.

#### Scenario: A wrong test path in the plan
- **WHEN** group 1 names a test path that is no file
- **THEN** the plan leaves the item out before the run with the path as its reason, so no step runs and no amendment is committed

#### Scenario: A second request for the same group
- **WHEN** the second step of group 1 stops with another valid request
- **THEN** the job applies nothing, the item is Blocked, and the comment quotes the request as a question

#### Scenario: A stop with no request
- **WHEN** a step stops and its last message holds no `plan-request` block
- **THEN** the job stops the item as it does for any stop

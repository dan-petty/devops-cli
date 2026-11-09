## ADDED Requirements

### Requirement: A pull request answer holds the title and the body
`PullStatus` SHALL hold the `title` and the `body` of the pull request, with empty defaults, and `get_pull_status` SHALL fill them from the answer of the pull request.

#### Scenario: A stage plan draft is read
- **WHEN** `read_draft` reads a stage plan pull status with title `docs(openspec): plan #3321 x` and body `x`
- **THEN** `draft.pull.title` is the title and `draft.pull.body` is the body

## MODIFIED Requirements

### Requirement: One function decides when a draft pull request is ready
`draft_readiness` SHALL take a draft pull request, its kind (stage plan, implement, agent or person), its recorded item, its check runs and its change folder, and SHALL answer ready, wait or refuse with a reason. A stage plan is complete when its title summary and its body are not placeholders. An implement pull request is complete when every task group is ticked and the change is archived. An agent's or a person's pull request is complete when its author says so.

#### Scenario: An incomplete implement pull request is refused
- **WHEN** the function reads a pull request of kind implement whose change has one unticked task group
- **THEN** it answers refuse and the reason names that group

#### Scenario: A complete plan with passing checks is ready
- **WHEN** the function reads a pull request of kind stage plan whose title summary and body are not placeholders and whose check runs all passed
- **THEN** it answers ready

#### Scenario: A stage plan with a placeholder title summary is refused
- **WHEN** the function reads a pull request of kind stage plan whose title is `docs(openspec): plan #3321 x` and whose body is not a placeholder
- **THEN** it answers refuse and the reason names a placeholder summary

#### Scenario: A stage plan with a placeholder body is refused
- **WHEN** the function reads a pull request of kind stage plan whose title summary is not a placeholder and whose body is `x`
- **THEN** it answers refuse and the reason names a placeholder body

#### Scenario: An author's pull request waits for the author
- **WHEN** the function reads a pull request of kind person or agent whose author has not said that it is complete
- **THEN** it answers wait

#### Scenario: Checks decide after completeness
- **WHEN** the function reads a complete pull request with one failed check, and another with one running check
- **THEN** it answers refuse for the first and wait for the second

#### Scenario: An extra check can refuse
- **WHEN** a test gives the function an extra check that refuses
- **THEN** it answers refuse with the reason of that check, even for a complete pull request with passing checks

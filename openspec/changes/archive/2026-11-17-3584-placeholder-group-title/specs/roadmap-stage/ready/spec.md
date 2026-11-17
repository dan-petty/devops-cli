## ADDED Requirements

### Requirement: Refusal of a placeholder group title on stage plan draft
`draft_readiness` SHALL refuse a `STAGE_PLAN` draft and name the group when its `change` holds a task group with a placeholder title. The stage ready row SHALL read `tasks.md` at the head commit of the plan pull request and pass its text in the `change` field of the `Draft`.

#### Scenario: A stage plan draft with a placeholder group title is refused
- **WHEN** `draft_readiness` receives a `STAGE_PLAN` `Draft` whose `change` holds a task group titled `x`
- **THEN** the result is `Answer.REFUSE` and its reason names the group

#### Scenario: The stage ready row reads tasks.md at the head commit
- **WHEN** the stage ready row settles a plan pull request
- **THEN** the `Draft` holds the `tasks.md` text of the head commit in `change`

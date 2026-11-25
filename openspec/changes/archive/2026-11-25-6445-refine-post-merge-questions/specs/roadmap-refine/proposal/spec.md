## MODIFIED Requirements

### Requirement: Only a person's decision waits on a person
A pre-build question of kind `person` SHALL be an open question with "(a person decides)", and the item SHALL wait on a person. Post-merge merge questions and post-release live-proof questions SHALL become no open question, and an open question with no "(a person decides)" mark SHALL NOT wait on a person.

#### Scenario: A decision that AGENTS.md reserves for a person
- **WHEN** the proposal asks "Which repository secret holds the key?" as a `person` question and the proposal passes its form check
- **THEN** the item waits on a person, the Open questions of its refine section hold "Which repository secret holds the key? (a person decides)", and the comment names Open questions

### Requirement: Refine limits person questions to owner-only acts
The refine reply prompt `src/devops_cli/ai/tasks/roadmap_refine_reply.md` SHALL list `a secret, a repository setting or a host` as `person`-kind decisions, SHALL contain no merge word in the `person`-kind sentence or `a review verdict`/`a milestone`, and SHALL name `Pending a person after the merge`.

#### Scenario: Refine reply prompt restricts person questions to owner-only decisions
- **WHEN** a test reads `src/devops_cli/ai/tasks/roadmap_refine_reply.md`
- **THEN** the `person` sentence contains `a secret, a repository setting or a host` with no `merge`, `a review verdict`, or `a milestone`, and the prompt contains `Pending a person after the merge`

## ADDED Requirements

### Requirement: A post-merge question converts to a pending-person criterion
`validate_proposal` MUST convert a `person` question asking who or when merges the pull request, record, ADR, change, or draft — or who runs or confirms a live proof after delivery — into an acceptance criterion named `Pending a person after the merge` with no open question.

#### Scenario: Merge and post-release live-proof questions leave no open question
- **WHEN** scripted proposals ask "Who merges the pull request?", "When does the pull request merge?", or "Who confirms the live proof after the merge and the release?" as `person` questions
- **THEN** `validate_proposal` returns no open question, adds one criterion named `Pending a person after the merge`, `check_ready` returns true, and `next_step_of` returns `ready`

### Requirement: Pre-build person questions still wait
`validate_proposal` MUST keep a `person` question open when its answer changes the pre-build plan, including a secret, a host, or a repository setting even if the question mentions merging.

#### Scenario: Pre-build person questions hold the item
- **WHEN** a proposal asks "Which secret holds the deploy key?", "Which repository setting enables the merge?", and "Which host runs the deploy?" as `person` questions
- **THEN** all three stay in `open_questions`, `check_ready` returns false, and `next_step_of` returns `person`

### Requirement: The refine rules date advances for post-merge handling
`CONST_ROADMAP_REFINE_RULES_SINCE` MUST be later than 2026-11-21 so existing waits created before this rule change are re-evaluated.

#### Scenario: The constant is later than 2026-11-21
- **WHEN** a test reads `CONST_ROADMAP_REFINE_RULES_SINCE` from `src/devops_cli/config/constants.py`
- **THEN** its timestamp is strictly greater than `2026-11-21T13:02:06Z`

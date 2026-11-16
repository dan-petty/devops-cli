## ADDED Requirements

### Requirement: One workflow label records each verdict of a bot pull request
The package SHALL declare the workflow labels `verdict/mergeable`, `verdict/fix-plan`, `verdict/fix-implementation`, `verdict/discard-plan`, `verdict/discard-implementation` and `verdict/issue-changed`. A plan pull request SHALL read `verdict/fix-plan` and `verdict/discard-plan`, and a delivery pull request SHALL read `verdict/fix-implementation` and `verdict/discard-implementation`. Both kinds SHALL read `verdict/mergeable` and `verdict/issue-changed`.

#### Scenario: The verdict labels of each kind
- **WHEN** the verdict labels of a plan and of a delivery are read
- **THEN** the plan reads `verdict/mergeable`, `verdict/fix-plan`, `verdict/discard-plan` and `verdict/issue-changed`, the delivery reads `verdict/mergeable`, `verdict/fix-implementation`, `verdict/discard-implementation` and `verdict/issue-changed`, and each label is a workflow label

### Requirement: The first verdict label scores a bot pull request
A bot pull request whose title starts with `docs(openspec): plan #` SHALL score stage, and each other bot pull request SHALL score implement. The first label event of a verdict label SHALL give the verdict of the pull request. A pull request with no such event SHALL be open. A first verdict label of the other kind SHALL leave the pull request unscored, and the read SHALL log why.

#### Scenario: A plan that needs a fix and then can merge
- **WHEN** the label events of a plan pull request are `type/docs`, `verdict/fix-plan` and `verdict/mergeable`, in this order, and the step fix-plan removed `verdict/fix-plan`
- **THEN** the verdict of the plan is needs fix

#### Scenario: A delivery with the label of a plan
- **WHEN** the label events of a delivery pull request are `type/feature`, `verdict/fix-plan` and `verdict/mergeable`
- **THEN** the delivery is unscored, and the read logs that its first verdict label is a label of the other kind

#### Scenario: The old label
- **WHEN** the label events of a plan pull request are `plan/needs-fix` and `verdict/mergeable`
- **THEN** the verdict of the plan is mergeable

### Requirement: eval grades reads the bot pull requests of the window with one search
`devops roadmap eval grades` SHALL read the pull requests that the bot of `service.github_app.slug` opened in the window, with their label events, in one GraphQL search for each 100 pull requests. `--repo` SHALL put the repository in the search.

#### Scenario: The search of the window and the repository
- **WHEN** a person runs `devops roadmap eval grades --repo example/app` at 2026-11-09T12:00:00Z with the slug `example-bot`
- **THEN** the command sends one GraphQL search for `is:pr author:app/example-bot created:>=2026-11-02T12:00:00Z repo:example/app`

#### Scenario: No slug
- **WHEN** `service.github_app.slug` is not set
- **THEN** the command sends no request to GitHub, and its text names `service.github_app.slug`

### Requirement: The report gives the verdict score beside the attempt ratio
For the stage and implement rows the report SHALL give the pull requests, the open and the unscored ones, the count and the share of each verdict over the pull requests with a verdict, the attempt ratio `p`, and the verdict score `(mergeable + w × needs fix) / (mergeable + needs fix + discards)`, where `w` is `roadmap.verdict_partial_score` (default 0.5). Issue changed SHALL stay out of the score.

#### Scenario: The score of stage
- **WHEN** the plan pull requests of the window have the first verdicts mergeable, mergeable, needs fix, discard plan and issue changed, and one plan has no verdict
- **THEN** the stage row gives 6 pull requests, 1 open, the share 0.4 of mergeable, and the score 0.625

#### Scenario: A delivery that needs a fix and a delivery with the label of a plan
- **WHEN** one delivery pull request has the first verdict label `verdict/fix-implementation` and one has `verdict/fix-plan`
- **THEN** the implement row gives 2 pull requests, 1 unscored, 1 needs fix and the score 0.5

#### Scenario: The partial score setting
- **WHEN** `roadmap.verdict_partial_score` is 1 and the plan pull requests have the first verdicts mergeable and needs fix
- **THEN** the stage score is 1.0

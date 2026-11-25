## MODIFIED Requirements

### Requirement: The first verdict label scores a bot pull request
A bot pull request whose title starts with `docs(spec): plan #` or legacy `docs(openspec): plan #` SHALL score stage, and each other bot pull request SHALL score implement. The first label event of a verdict label SHALL give the verdict of the pull request. A pull request with no such event SHALL be open. A first verdict label of the other kind SHALL leave the pull request unscored, and the read SHALL log why.

#### Scenario: A plan that needs a fix and then can merge
- **WHEN** the label events of a plan pull request are `type/docs`, `verdict/fix-plan` and `verdict/mergeable`, in this order, and the step fix-plan removed `verdict/fix-plan`
- **THEN** the verdict of the plan is needs fix

#### Scenario: A delivery with the label of a plan
- **WHEN** the label events of a delivery pull request are `type/feature`, `verdict/fix-plan` and `verdict/mergeable`
- **THEN** the delivery is unscored, and the read logs that its first verdict label is a label of the other kind

#### Scenario: The old label
- **WHEN** the label events of a plan pull request are `plan/needs-fix` and `verdict/mergeable`
- **THEN** the verdict of the plan is mergeable

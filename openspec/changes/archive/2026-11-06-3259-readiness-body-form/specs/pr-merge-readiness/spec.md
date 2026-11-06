## REMOVED Requirements

### Requirement: A long pull request body gets a warning
**Reason**: `body_problems` limits the body to the same 1,000 characters and now blocks, so the warning would report one fault twice (#3259).
**Migration**: The requirement "Every problem of the body is one blocker" holds the rule.

### Requirement: The body warning blocks nothing
**Reason**: The length of the body is now one rule of the form, and a body that breaks the form blocks (#3259).
**Migration**: The requirement "A pull request body must keep the form" holds the exit code.

## ADDED Requirements

### Requirement: A pull request body must keep the form
`devops pr check-readiness` SHALL call `body_problems` on the body of the pull request, where the base holds `openspec/changes/` and the title is no plan title. A body that GitHub reports as `null` SHALL count as empty. The command SHALL exit 1 when `body_problems` returns at least one problem.

#### Scenario: A body with no closing line
- **WHEN** the body has no line `Closes #<issue>` and nothing else blocks the pull request
- **THEN** `devops pr check-readiness` prints the missing-`Closes` problem and exits 1

#### Scenario: A body in the form
- **WHEN** the body keeps the form and nothing else blocks the pull request
- **THEN** `devops pr check-readiness` prints the success line and exits 0

#### Scenario: A base without change folders
- **WHEN** the base holds no `openspec/changes/`
- **THEN** the verdict holds no body blocker

#### Scenario: A plan pull request
- **WHEN** the title is a plan title
- **THEN** the verdict holds no blocker of the kind body form

### Requirement: Every problem of the body is one blocker
The verdict SHALL hold one blocker of the kind body form for each problem that `body_problems` returns, in its order. Each blocker SHALL name the pull request number and hold the text of the problem.

#### Scenario: A body with two problems
- **WHEN** the body has no line `Closes #<issue>` and no line `Change:`
- **THEN** the verdict holds two blockers of the kind body form, one for each missing line

#### Scenario: A long body
- **WHEN** the text of the body is longer than 1,000 characters
- **THEN** the verdict holds a blocker of the kind body form that names the length and the limit

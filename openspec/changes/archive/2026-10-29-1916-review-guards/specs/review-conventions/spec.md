## Purpose

Which project files a review copies with the code it reviews, and which file a generated AGENTS.md routes a review to: a defect corpus and a pull request checkout carry the source project's `AGENTS.md` and no review guards file.

## ADDED Requirements

### Requirement: A defect corpus carries no review guards file
`devops review corpus generate` SHALL copy the conventions file of the source project into the corpus and SHALL write no `.devops/review.md`, also when the source project keeps one.

#### Scenario: A source in a repository that keeps review guards
- **WHEN** `devops review corpus generate` runs on a source inside a repository that holds `AGENTS.md` and `.devops/review.md`
- **THEN** the corpus holds the text of that `AGENTS.md` and no `.devops/review.md`

### Requirement: A pull request checkout takes no review guards file from its base
The checkout of a pull request review SHALL take `AGENTS.md` and its peer files from the base commit, and SHALL neither read nor write `.devops/review.md` from the base.

#### Scenario: A base that keeps review guards
- **WHEN** a pull request whose base holds `AGENTS.md` and `.devops/review.md` is checked out for a review
- **THEN** the checkout holds the base's `AGENTS.md`, holds no `.devops/review.md`, and no request reads `.devops/review.md`

### Requirement: A generated AGENTS.md routes no task to a review guards file
`devops ai agents` SHALL write an `AGENTS.md` that names no `.devops/review.md`, also in a project that keeps one.

#### Scenario: A project that keeps review guards
- **WHEN** the agent instructions are scaffolded in a project that holds `.devops/review.md`
- **THEN** the generated `AGENTS.md` does not name `.devops/review.md`

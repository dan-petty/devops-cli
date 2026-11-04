## ADDED Requirements

### Requirement: The job runs a project step only where the target declares it
The job SHALL run the docs step and the archive step only when the default branch of the target repository declares the step in `.devops/roadmap.toml` under `[implement.steps]`. The job SHALL read the file from the default branch and SHALL NOT read the checkout. A default branch with no file SHALL declare no step. A file that is not valid SHALL stop the item and run no step.

#### Scenario: A target with no declaration skips the docs step
- **WHEN** the default branch of the target holds no `.devops/roadmap.toml` and the job reaches `_finish_change` or `_scoped_rounds`
- **THEN** the job runs no docs command and the job ends with a pull request

#### Scenario: A target with no declaration skips the archive step
- **WHEN** the default branch of the target holds no `.devops/roadmap.toml` and the job reaches `_finish_change`
- **THEN** the job archives no change folder and does not fail, and the pull request is ready with the change not archived

#### Scenario: An agent edit of the declaration changes no step
- **WHEN** an agent adds or removes the declaration in the checkout and the default branch is unchanged
- **THEN** the job runs the steps that the default branch declares and no other

#### Scenario: A target that declares the steps runs them
- **WHEN** the default branch declares `docs = true` and `archive = true`
- **THEN** the job runs the docs command and archives the change folder

#### Scenario: A declaration that is not valid
- **WHEN** the file on the default branch names a step that does not exist
- **THEN** the job stops the item with the path of the file in the reason and runs no step

### Requirement: The comment of the job names each skipped step
The comment of the job on the pull request SHALL name each step that the job skipped and the file that did not declare it.

#### Scenario: Steps skipped
- **WHEN** the job skips the docs step and the archive step
- **THEN** the comment lists `step docs` and `step archive` as skipped

#### Scenario: Steps run
- **WHEN** the job runs both steps
- **THEN** the comment names no skipped step

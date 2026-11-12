## ADDED Requirements

### Requirement: pr ready does not wait for checks in a repository with no CI
When the head commit of the pull request reports no check run and no commit status, and the repository has no GitHub Actions workflow, no check will start. Then `devops pr ready` SHALL say so, SHALL NOT judge the checks or warn of them, and SHALL mark the pull request ready with no `--force`.

#### Scenario: A repository with no CI
- **WHEN** the head commit reports no check and the repository has no workflow
- **THEN** `pr ready` names the repository, says that it has no GitHub Actions workflow, marks the pull request ready, and exits 0 with no warning about "no checks reported"

### Requirement: pr ready waits for checks that a workflow can start
When the head commit reports no check and the repository has a GitHub Actions workflow, `devops pr ready` SHALL wait for the checks as before. A read of the workflows that fails SHALL stop the command with exit 1 and the error.

#### Scenario: Checks that have not started
- **WHEN** the head commit reports no check and the repository has 2 workflows
- **THEN** `pr ready` exits 8 and marks nothing

#### Scenario: The workflows cannot be read
- **WHEN** the head commit reports no check and GitHub answers the read of the workflows with an error
- **THEN** `pr ready` exits 1 and marks nothing

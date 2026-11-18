# rag-drift Specification

## Purpose
The drift check that compares the working tree and the Qdrant points of one project, and the project name that the check reads for its points, its cache entries and its report.

## Requirements

### Requirement: Drift takes the project name of the repo option
`devops ai rag drift` SHALL compare the project that the option `--repo owner/name` names when the user gives it, and the name of the directory that it runs in otherwise.

#### Scenario: Drift runs outside the checkout
- **WHEN** The user runs `devops ai rag drift` with the option `--repo owner/name` from a directory that holds another name
- **THEN** The report names the project owner/name and reads its points and its cache entries.

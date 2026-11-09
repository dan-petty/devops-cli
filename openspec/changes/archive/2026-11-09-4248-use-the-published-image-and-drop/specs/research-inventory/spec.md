# Spec Delta

## ADDED Requirements

### Requirement: The inventory reads the lock of each devcontainer configuration folder
`devops research inventory` SHALL read the devcontainer lock `.devcontainer/devcontainer-lock.json` and the lock `.devcontainer/<folder>/devcontainer-lock.json` of each configuration folder, and SHALL name the file of each feature pin from the repository root.

#### Scenario: A lock in a configuration folder
- **WHEN** a repository has only `.devcontainer/image/devcontainer-lock.json`, which pins one feature
- **THEN** the inventory lists one devcontainer feature component
- **AND** its file is `.devcontainer/image/devcontainer-lock.json` and its line is the line of the feature key

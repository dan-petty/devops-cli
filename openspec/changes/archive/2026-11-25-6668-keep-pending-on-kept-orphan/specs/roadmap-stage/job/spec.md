## MODIFIED Requirements

### Requirement: The cleanup of a stage round comes before any create
Before any create, the round SHALL clean the orphans and the staged branches of closed items, keeping an App-only branch and `stage.pending` mark of a `Ready` orphan and deleting other orphans, and write the rejections of the items that it does not submit. The selection SHALL read the heads without the branches of the orphans that the round cleans.

#### Scenario: An old orphan
- **WHEN** a Ready item holds an intent mark of 2 hours and a pushed branch with no pull request
- **THEN** the round keeps the App-only branch and `stage.pending` mark and creates the Job of the item in the same round

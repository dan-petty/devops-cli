## MODIFIED Requirements

### Requirement: Each line has the number, the age and one clearing step
Each line SHALL show the number of its issue or pull request (`-` when it has none), the time since its last update, and the one command or action that clears it. A pull request of a job SHALL be cleared by a review and a merge at its gate, the release pull request by a merge, a stopped item by the comment `implement: retry`, an old claim by `devops roadmap release`, and missing labels by `devops gh label sync`.

#### Scenario: The command of a line
- **WHEN** the inbox lists an old claim of #7 and missing labels
- **THEN** the claim line shows `#7`, an age, and `devops roadmap release 7 --repo <repo> --confirm`, and the labels line shows `devops gh label sync --repo <repo>`

#### Scenario: The cause of a block
- **WHEN** a blocked item records `implement.stopped` as `group 2`
- **THEN** its line shows `group 2` as the cause and the retry comment as the step

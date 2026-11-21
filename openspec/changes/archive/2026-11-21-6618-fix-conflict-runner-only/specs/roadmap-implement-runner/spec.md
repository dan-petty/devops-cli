## ADDED Requirements

### Requirement: A network git call writes the refs of the clone with its hooks off
`OriginGit` SHALL write each remote-tracking ref of a fetch or a push into the clone with `-c core.hooksPath=/dev/null`, so no hook of the clone runs.

#### Scenario: A reference-transaction hook of the clone
- **WHEN** the clone holds a `reference-transaction` hook, and the job fetches `main` and pushes a branch
- **THEN** the hook does not run, and the branch is on `origin`

### Requirement: A fetch can deepen a shallow clone
`OriginGit.fetch` SHALL take `deepen`, which adds that many commits below the boundary of a shallow clone (`--deepen`). A fetch that removes the `shallow` file of the new git folder SHALL remove the `shallow` file of the clone, so the clone holds the whole history.

#### Scenario: A deepening that reaches the first commit
- **WHEN** the clone was made with `--depth 1`, and the job fetches `main` with `deepen=50` on a history of three commits
- **THEN** the clone is no longer shallow, and `origin/main` reaches all three commits

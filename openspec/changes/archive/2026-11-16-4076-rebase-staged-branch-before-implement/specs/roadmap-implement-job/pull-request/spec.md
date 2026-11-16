## ADDED Requirements

### Requirement: The option skips the fetch and the rebase
`devops roadmap implement` SHALL accept a `--no-rebase` option that skips the fetch of the default branch and the rebase of the branch before the first step and before the push.

#### Scenario: The option skips both syncs
- **WHEN** a runner Job runs `roadmap implement --repo <owner/name> --item 7 --confirm --no-rebase` in a real repository whose `origin/main` holds a commit that the branch lacks
- **THEN** the worktree gets no `git fetch -q origin main` and no `git rebase` at the start or before the push, the branch keeps its commits, and the job pushes them with the lease

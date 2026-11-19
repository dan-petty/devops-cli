## ADDED Requirements

### Requirement: A git child that reaches a remote gets the GitHub credential helper
The process runner SHALL give each git child that reaches a remote the two `-c` values of `CONST_GIT_GITHUB_CREDENTIAL_CONFIG`, after the `git` word and before the subcommand, so that `gh auth git-credential` reads the `GH_TOKEN` that the same call pins on that child.

#### Scenario: The reproduction form with a token
- **WHEN** a test runs `git -C <clone> ls-remote --heads origin main` through the process runner with the session's token and a child that records its arguments
- **THEN** the recorded arguments hold the two `-c` values of `CONST_GIT_GITHUB_CREDENTIAL_CONFIG` after `git` and before `ls-remote`, and the environment of the child holds `GH_TOKEN`.

#### Scenario: A fetch with prune
- **WHEN** a test runs `git fetch --prune origin` through the process runner with the session's token and a child that records its arguments
- **THEN** the recorded arguments hold the two `-c` values after `git` and before `fetch`, and the environment of the child holds `GH_TOKEN`.

### Requirement: A git child that reaches no remote gets no credential helper
The process runner MUST NOT give the credential helper or a GitHub token to a git child that reaches no remote.

#### Scenario: A local status
- **WHEN** a test runs `git status` through the process runner with `GH_TOKEN` in the environment of the process
- **THEN** the recorded arguments hold no `-c` credential value, and the environment of the child holds no `GH_TOKEN`.

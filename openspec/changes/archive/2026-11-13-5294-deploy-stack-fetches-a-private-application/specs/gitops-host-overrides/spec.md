## ADDED Requirements

### Requirement: deploy-stack fetches an Application repository with the GitHub session credential
`render_at_revision` SHALL give `git fetch` the `-c` values `credential.https://github.com.helper=` and `credential.https://github.com.helper=!gh auth git-credential`, in this order and before the subcommand. The empty value clears the helpers of the config files for github.com, so `gh auth git-credential` gives git the token that the process runner pins on a git child that reaches a remote. Thus `devops k8s deploy-stack` renders an Application that names a private repository on github.com.

#### Scenario: An Application names a private repository on github.com
- **WHEN** `render_at_revision` fetches `https://github.com/example/private-repository` at `main`
- **THEN** the `-c` values of the fetch name the helpers `""` and `!gh auth git-credential` for `https://github.com`, in this order
- **AND** `git_reaches_remote` is true for the arguments of the fetch, so the process runner gives it the session's token

#### Scenario: Only the fetch gets git options
- **WHEN** `render_at_revision` renders the SSH remote `ssh://git@example.com/repository.git`
- **THEN** the fetch holds the `-c` values `core.sshCommand=ssh -o BatchMode=yes`, `credential.https://github.com.helper=` and `credential.https://github.com.helper=!gh auth git-credential`, and no other command holds `-c`
- **AND** the environment of each command holds `GIT_TERMINAL_PROMPT=0` and no other key

## MODIFIED Requirements

### Requirement: deploy-stack fetches an Application repository with the GitHub session credential
`render_at_revision` SHALL give `git fetch` no credential `-c` value. git gets a github.com credential from the helper that it is configured with: the devcontainer and the images set `gh auth git-credential`, which reads the token that the process runner pins on each git child. Thus `devops k8s deploy-stack` renders an Application that names a private repository on github.com.

#### Scenario: An Application names a private repository on github.com
- **WHEN** `render_at_revision` fetches `https://github.com/example/private-repository` at `main`
- **THEN** the fetch holds no `-c` value that names a credential, and its last two arguments are the URL and the revision

#### Scenario: Only the fetch gets git options
- **WHEN** `render_at_revision` renders the SSH remote `ssh://git@example.com/repository.git`
- **THEN** the fetch holds the one `-c` value `core.sshCommand=ssh -o BatchMode=yes`, and no other command holds `-c`
- **AND** the environment of each command holds `GIT_TERMINAL_PROMPT=0` and no other key

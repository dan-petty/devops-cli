## RENAMED Requirements

- FROM: `### Requirement: A git child gets no -c value, and a git child that reaches no remote gets no token`
- TO: `### Requirement: A git child gets no -c value`

- FROM: `### Requirement: A network git child with no token fails at once only for the App`
- TO: `### Requirement: A git child with no token fails at once only for the App`

## MODIFIED Requirements

### Requirement: A child that gets the session's token stops with its process group
The process runner SHALL start each child that gets the session's token in a session of its own. A timeout, or another error while the child runs, SHALL kill the whole process group of the child. After a Ctrl+C, the process runner SHALL first send SIGINT to the process group of the child, which the terminal does not reach, and wait up to 0.25 s, as `subprocess.run` waits after a Ctrl+C, before it kills what is left of the group.

#### Scenario: A timeout
- **WHEN** a git child starts a helper and runs past its timeout
- **THEN** the call raises `subprocess.TimeoutExpired`, and neither the child nor the helper is alive

#### Scenario: A Ctrl+C during a git commit
- **WHEN** `git commit -a` runs a `pre-commit` hook that sleeps, and the process gets SIGINT
- **THEN** the call raises `KeyboardInterrupt`, and `.git/index.lock` is gone

### Requirement: A git child gets no -c value
The process runner MUST NOT add a `-c` value to the arguments of a git child.

#### Scenario: A local status
- **WHEN** a test runs `git status`, `git fetch --prune origin` or `git -C clone ls-remote --heads origin main` through the process runner with `GH_TOKEN` in the environment of the process
- **THEN** the recorded arguments of the child are the arguments of the caller with no `-c` value, and the child gets the session's token as `GH_TOKEN`

### Requirement: A git child with no token fails at once only for the App
When the process acts as the GitHub App, holds no installation token that has not expired, and the mint fails, the process runner SHALL raise the error of the mint before it starts a git child. For a person, such a child SHALL start with no `GH_TOKEN`, and the git children SHALL keep that failed lookup for the life of the process. A gh call SHALL look again, and the next git child SHALL get the token that it finds.

#### Scenario: The App's mint fails
- **WHEN** the environment holds `not-a-pem-key` as the App's key and the process runner starts `git fetch origin` or `git status`
- **THEN** it raises `GitHubUnauthenticatedError` that says the App has no installation token, and no child starts

#### Scenario: A person has no login
- **WHEN** no token resolves and the process runner starts `git fetch` two times, then `gh issue list` after `gh auth login`, then `git fetch`
- **THEN** the first two git children start with no `GH_TOKEN` after one `gh auth token`, the gh call looks the token up again, and the last git child gets that token

## REMOVED Requirements

### Requirement: Only a git child that reaches a remote gets the session's token
**Reason**: The runner Job runs the agent in its own container, with no App key and no token (#3700). So no program of the agent reads the token of a local git child, and the parser of the git arguments protects nothing more (#6691).
**Migration**: The requirement "Each gh and git child gets the session's token as GH_TOKEN" replaces it.

### Requirement: A gh child reads the session's token from a private configuration folder
**Reason**: The private folder kept the token from a `--jq` filter and from a process of the same user. In the runner Job, no program of the agent runs in a container that holds a token (#3700, #6691).
**Migration**: The requirement "Each gh and git child gets the session's token as GH_TOKEN" replaces it.

### Requirement: The folder of a gh child does not depend on the current folder
**Reason**: The process runner makes no folder for a gh child (#6691).
**Migration**: None.

### Requirement: A candidate folder that is a link or in the current folder is skipped
**Reason**: The process runner makes no folder for a gh child (#6691).
**Migration**: None.

### Requirement: An async gh call makes its folder after the token lookup
**Reason**: The process runner makes no folder for a gh child (#6691). An async call still looks up the token in a thread.
**Migration**: None.

### Requirement: In a runner, the leftover processes end before and after each child that gets the session's token
**Reason**: The agent phase runs in its own container, which holds no token, and its processes end with that container (#3700). So no process of the agent lives next to a child that gets the token (#6691).
**Migration**: None.

## ADDED Requirements

### Requirement: Each gh and git child gets the session's token as GH_TOKEN
The process runner SHALL give each gh child, except a local gh command (`gh auth`, version and help), and each git child the session's token as `GH_TOKEN`, and no `GITHUB_TOKEN`. It SHALL make no configuration folder for a gh child. A local gh command SHALL get the `GH_TOKEN` and `GITHUB_TOKEN` of the environment, or of the caller, unchanged.

#### Scenario: A git child
- **WHEN** the process runner starts `git push origin feat/184-example`, `git -C work/example fetch origin main`, `git ls-remote --heads origin`, `git add -A`, `git -c user.name=example commit -q -m fix` and `git remote get-url origin`, with `GH_TOKEN` in the environment of the process and `GITHUB_TOKEN` from the caller
- **THEN** each child gets the session's token as `GH_TOKEN`, and no `GITHUB_TOKEN` and no `GH_CONFIG_DIR`

#### Scenario: A gh child
- **WHEN** the process runner starts `gh api rate_limit`, with `GH_TOKEN` in the environment of the process and `GITHUB_TOKEN` from the caller
- **THEN** the child gets the session's token as `GH_TOKEN`, and no `GITHUB_TOKEN` and no `GH_CONFIG_DIR`

#### Scenario: The App's installation token
- **WHEN** the process acts as the App and starts a gh child
- **THEN** the child gets the installation token as `GH_TOKEN`

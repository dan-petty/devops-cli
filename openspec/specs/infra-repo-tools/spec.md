# infra-repo-tools Specification

## Purpose
How the devcontainer installs the tools of each infra repo: `devops devcontainer post-start` runs the install command of the project profile of each entry of `infra.repos` in its checkout, so the versions stay those that the repository pins.

## Requirements

### Requirement: Post-start installs the tools of each infra repo
`devops devcontainer post-start` SHALL run `tools.install` of the project profile of each entry of `infra.repos` in its checkout, with the bound `DEFAULT_INFRA_TOOLS_INSTALL_TIMEOUT_SECONDS`, and SHALL print one line for each repo. The checkout SHALL be the `path` of the entry, else `<repos.base_dir>/<owner>/<name>`.

#### Scenario: Two infra repos
- **WHEN** `infra.repos` names two repos whose checkouts have `ansible.cfg` and no project file
- **THEN** `make install` runs in each checkout, in the order of the entries, and each line names the repo, its checkout and the command

#### Scenario: The project file names another command
- **WHEN** `.devops/project.toml` of the checkout sets `[tools] install = ["just", "tools"]`
- **THEN** `just tools` runs in the checkout

### Requirement: A failed install is a warning
A missing checkout, an invalid project file, a failed command or a command past its bound SHALL give a warning line, the next repo SHALL go on, and post-start SHALL exit 0. An empty `tools.install` SHALL run nothing.

#### Scenario: A missing checkout
- **WHEN** the checkout of the first repo does not exist
- **THEN** the first line is a warning that names the checkout, and the install of the second repo runs

#### Scenario: A failed install
- **WHEN** the install of the first repo exits with code 2
- **THEN** its line is a warning with the code and the last line of the output, the install of the second repo runs, and post-start exits 0

#### Scenario: An install past its bound
- **WHEN** the install does not end in 600 s
- **THEN** its line is a warning that names the bound

### Requirement: The dry run plans each install
The dry run of `devops devcontainer post-start` SHALL list the install command of each infra repo whose checkout has a valid profile with a command, and SHALL run no command.

#### Scenario: The plan of one infra repo
- **WHEN** `devops devcontainer post-start --dry-run --json` runs with one infra repo
- **THEN** the requests hold `make install` with the target of the repo and the condition that names its checkout, and no process runs

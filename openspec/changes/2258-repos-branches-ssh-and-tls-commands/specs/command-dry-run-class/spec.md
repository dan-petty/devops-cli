## ADDED Requirements

### Requirement: git-workspace-request-plans
The seven commands `branches sync`, `branches update`, `repos clone`, `repos clone-org`, `repos sync`, `repos update` and `repos worktrees prune` SHALL carry the `request-plan` dry-run class and SHALL expose `--dry-run`, in the forms `devops <command> --dry-run` and `devops --dry-run <command>`. A dry run SHALL make no external request and SHALL print the requests of the real run, numbered, in the order of the real run.

#### Scenario: Dry run on branches sync
- **WHEN** user executes `devops branches sync --dry-run` for a workspace with one repository whose remote is `origin` and whose current branch tracks `origin`
- **THEN** no `git fetch` and no `git pull` runs, and the output lists `git -C <repo> fetch --prune origin` and then `git -C <repo> pull origin <branch>`

#### Scenario: A dry run refuses what a run refuses
- **WHEN** user executes `devops repos clone -- -bad --dry-run`
- **THEN** the command exits with status 1 and lists no request

#### Scenario: Dry run on repos update through the root flag
- **WHEN** user executes `devops --dry-run repos update --no-pull`
- **THEN** no git command that changes state runs, the output lists one `git fetch --prune` for each remote of each repository and no `git pull`, and the last line is the `code --reuse-window` command that reloads the workspace

#### Scenario: Dry run on repos clone
- **WHEN** user executes `devops repos clone https://github.com/example-org/app.git --dry-run`
- **THEN** nothing is cloned, `known_hosts` is not changed, and the output lists `git clone -- https://github.com/example-org/app.git <base-dir>/example-org/app` and then the `code --reuse-window` command

#### Scenario: Dry run on repos clone-org
- **WHEN** user executes `devops repos clone-org example-org --dry-run`
- **THEN** GitHub receives no request, and the output lists the listing request `GET /orgs/example-org/repos`, the fallback listing for the own account with its condition, and a `git clone` for each listed repository with the repeat `for each listed repository`

#### Scenario: Dry run on repos worktrees prune
- **WHEN** user executes `devops repos worktrees prune --dry-run`
- **THEN** GitHub receives no request, and the output lists `GET /repos/<repo>/commits/<sha>/pulls` for each worktree that local state does not decide

#### Scenario: The plan matches the real run
- **WHEN** a test runs `devops repos sync` on a `git_fake` that answers the local reads, and compares the git commands that are not local reads with the plan of `devops repos sync --dry-run`
- **THEN** the commands and the plan lines are the same, in the same order

### Requirement: git-workspace-no-external-request
The five commands `branches clean`, `branches jira`, `branches list`, `repos list` and `repos worktrees status` SHALL carry the `no-external-request` dry-run class. `branches list`, `repos list` and `repos worktrees status` SHALL run normally under `devops --dry-run` and have no `--dry-run` option. `branches clean` and `branches jira` SHALL preview under `--dry-run` and change nothing.

#### Scenario: Dry run on branches list
- **WHEN** user executes `devops --dry-run branches list --base-dir <dir>`
- **THEN** the command lists the branches of each repository and starts only git commands that read

#### Scenario: Dry run on repos list
- **WHEN** user executes `devops --dry-run repos list`
- **THEN** the command lists the cloned repositories and prints no JSON preview

#### Scenario: repos list has no dry-run option
- **WHEN** user executes `devops repos list --dry-run`
- **THEN** the command exits with status 2 and reports `No such option: --dry-run`

#### Scenario: Dry run on repos worktrees status
- **WHEN** user executes `devops --dry-run repos worktrees status`
- **THEN** the command lists the worktrees and starts only git commands that read

#### Scenario: Dry run on branches clean
- **WHEN** user executes `devops --dry-run branches clean --base-dir <dir>` for a repository with a merged branch
- **THEN** the output says that it would delete the branch and no branch is deleted

#### Scenario: Dry run on branches jira with a bad ticket
- **WHEN** user executes `devops branches jira bad --dry-run`
- **THEN** the command exits with status 1, as a run does

#### Scenario: Dry run on branches jira
- **WHEN** user executes `devops --dry-run branches jira PROJ-1 --repo <repo>`
- **THEN** the output says that it would create the branch `feature/PROJ-1` and no `git checkout` runs

### Requirement: ssh-request-plans
The commands `ssh register` and `ssh rotate` SHALL carry the `request-plan` dry-run class and SHALL expose `--dry-run`. A dry run SHALL make no request to GitHub, start no process, and print the requests of the real run in order.

#### Scenario: Dry run on ssh register
- **WHEN** user executes `devops ssh register --dry-run` and `devops --dry-run ssh register`
- **THEN** `github_api` receives no request, no process starts, and the output lists `POST /user/keys` and `POST /user/ssh_signing_keys` with the key as a placeholder, the listing of each endpoint with the condition that the `POST` answers HTTP 422, and the `git config` commands that point git signing at the key

#### Scenario: Dry run on ssh rotate
- **WHEN** user executes `devops ssh rotate --dry-run`
- **THEN** no key file is written, `github_api` receives no request, and the output lists the same requests with the condition that the key is old enough or `--force` is set

#### Scenario: The plan matches the real run
- **WHEN** a test runs `devops ssh register` against `github_api` routes that accept both keys, and compares the requests that it received with the plan lines that have no condition
- **THEN** the methods and the paths are the same, in the same order

### Requirement: ssh-no-external-request
The commands `ssh audit`, `ssh generate`, `ssh list` and `ssh status` SHALL carry the `no-external-request` dry-run class. `ssh audit`, `ssh list` and `ssh status` SHALL run normally under `devops --dry-run` and SHALL have no `--dry-run` option. `ssh generate` SHALL provide a local preview under `--dry-run` that writes no key.

#### Scenario: Dry run on ssh list
- **WHEN** user executes `devops --dry-run ssh list --key-dir <dir>` for a directory with one managed key
- **THEN** the command prints the table of the key, starts no process and sends no request

#### Scenario: ssh status has no dry-run option
- **WHEN** user executes `devops ssh status --dry-run`
- **THEN** the command exits with status 2 and reports `No such option: --dry-run`

#### Scenario: Dry run on ssh generate
- **WHEN** user executes `devops ssh generate --key-dir <dir> --dry-run`
- **THEN** the output says which key file it would write, and neither the private key nor the public key exists afterwards

### Requirement: tls-request-plans
The command `tls enable-k8s` SHALL carry the `request-plan` dry-run class and SHALL expose `--dry-run`. A dry run SHALL start no process and print the kubectl requests of the real run, for each namespace in order.

#### Scenario: Dry run on tls enable-k8s
- **WHEN** user executes `devops tls enable-k8s --namespace web --namespace db --dry-run` and `devops --dry-run tls enable-k8s --namespace web --namespace db`
- **THEN** `process_fake` records no call, and the output lists, for `web` and then for `db`: `kubectl get namespace`, `kubectl create namespace` with the condition that the namespace does not exist, `kubectl create secret tls ... --dry-run=client -o yaml`, and `kubectl apply -f -` with the rendered secret as a placeholder on standard input

#### Scenario: Dry run with a context
- **WHEN** user executes `devops tls enable-k8s --context example --namespace web --dry-run`
- **THEN** each listed kubectl command ends with `--context example`

#### Scenario: The plan matches the real run
- **WHEN** a test runs `devops tls enable-k8s --namespace web` on a `process_fake` that answers `get namespace` with status 1 and the other calls with status 0, and compares the recorded argv with the plan
- **THEN** the four recorded commands and the four plan lines are the same, in the same order

### Requirement: tls-no-external-request
The commands `tls ca`, `tls cert`, `tls homelab`, `tls inspect` and `tls verify` SHALL carry the `no-external-request` dry-run class. `tls inspect` and `tls verify` SHALL run normally under `devops --dry-run`. `tls ca`, `tls cert` and `tls homelab` SHALL provide a local preview under `--dry-run` that writes no key and no certificate.

#### Scenario: Dry run on tls inspect
- **WHEN** user executes `devops --dry-run tls inspect <certificate>`
- **THEN** the command prints the table of the certificate

#### Scenario: Dry run on tls ca
- **WHEN** user executes `devops tls ca --output-dir <dir> --dry-run`
- **THEN** the output says which files it would write, and `<dir>` holds no `ca.crt` and no `ca.key`

#### Scenario: Dry run on tls homelab through the root flag
- **WHEN** user executes `devops --dry-run tls homelab --output-dir <dir>`
- **THEN** the output says which bundle it would write, and `<dir>` is empty or absent

## Purpose

How every clone under repos/ keeps a gitea remote at https://git.<domain> next to origin, created on gitea when missing, with GitHub's default branch carried over by devops repos sync.

## ADDED Requirements

### Requirement: Gitea URL validation
The configuration SHALL define the settings `gitea.url`, `gitea.username`, `gitea.github_branches` and `gitea.extra_checkouts`, and the credential `gitea.token`; `gitea.url` SHALL be unset by default and SHALL accept only an `https://` URL with no path.

#### Scenario: An HTTP URL is refused
- **WHEN** `gitea.url` is set to `http://git.example.com`
- **THEN** settings validation raises an error and no token is sent

### Requirement: Gitea branch settings defaults
`gitea.github_branches` SHALL default to `["main"]` and `gitea.extra_checkouts` SHALL default to an empty list.

#### Scenario: The defaults load
- **WHEN** a config file sets no `gitea` keys
- **THEN** the settings hold `["main"]` and `[]`

### Requirement: Gitea token credential
`gitea.token` SHALL be a `Credential` in `CREDENTIALS` with keyring name `gitea_token` and environment variable `DEVOPS_CLI_GITEA_TOKEN`.

#### Scenario: The token comes from the keyring
- **WHEN** `gitea.token` is unset in the config file and the keyring holds `gitea_token`
- **THEN** the credential resolver returns the keyring value for `gitea.token`

### Requirement: Hidden token prompt
`devops config set gitea.token` SHALL prompt for the token with hidden input when the value is omitted.

#### Scenario: The token is typed at a hidden prompt
- **WHEN** `devops config set gitea.token` runs without a value
- **THEN** the command reads the token at a hidden prompt and stores it in the keyring

### Requirement: Gitea client base
The Gitea client SHALL wrap one `httpx2.Client` from `devops_cli.http.entry.http_client` at `configured_level()`.

#### Scenario: The client builds a version request
- **WHEN** `version()` is called against a `MockTransport`
- **THEN** the request URL is `<gitea.url>/api/v1/version`

### Requirement: Gitea client headers
The Gitea client SHALL use `base_url` `gitea.url` plus `/api/v1` and the header `Authorization: token <token>`.

#### Scenario: The client sends the token
- **WHEN** `current_user()` is called
- **THEN** the request carries `Authorization: token <token>`

### Requirement: Gitea client paths and TLS
The Gitea client SHALL build request paths from path segments and SHALL verify TLS against the system store.

#### Scenario: A path segment is escaped
- **WHEN** `repo` is called with an owner that holds a slash
- **THEN** the client builds the path from segments and sends no malformed URL

### Requirement: Gitea client typed calls
The Gitea client SHALL provide typed calls for `version`, `current_user`, `org`, `create_org`, `repo`, `create_repo`, `branch_protections` and `create_branch_protection`.

#### Scenario: A repository is created for the token's login
- **WHEN** `create_repo` runs with an owner equal to `current_user.login`
- **THEN** the client sends `POST /api/v1/user/repos` with `private: true` and `auto_init: false`

### Requirement: Cloudflare Access blocked
The Gitea client SHALL not follow redirects; it SHALL raise `GiteaAccessBlocked` for a redirect to another host or a 403 with `cf-mitigated: challenge`, naming the bypass policy and pointing to the guide in `k8s/README.md`.

#### Scenario: Cloudflare Access refuses a request
- **WHEN** the transport returns a 302 to another host or a 403 with `cf-mitigated: challenge`
- **THEN** `GiteaAccessBlocked` names the bypass policy and the guide, and the token never appears in the message

### Requirement: Gitea errors mask the token
The Gitea client SHALL raise `GiteaError` for any other status, naming the call, the repository and Gitea's `message`, with the token masked by `mask_secrets`.

#### Scenario: Gitea returns an error
- **WHEN** `create_repo` gets HTTP 500 with a message that holds the token
- **THEN** `GiteaError` names the call and the repository and the message masks the token

### Requirement: Connect validates before token
`devops repos gitea connect` SHALL validate the URL before it reads the token.

#### Scenario: An HTTP URL is refused before a request
- **WHEN** `connect --url http://git.example.com` runs
- **THEN** the command exits 1, makes no request on the `MockTransport` and reads no keyring value

### Requirement: Connect checks and saves
`devops repos gitea connect` SHALL check `version` and `current_user`, save `gitea.url` and `gitea.username`, and print the URL, login and version.

#### Scenario: Connect saves the login
- **WHEN** `connect --url https://git.example.com` runs with a valid token
- **THEN** the command saves `gitea.url` and `gitea.username` and prints the URL, login and version

### Requirement: Connect says to refresh remotes
`devops repos gitea connect` SHALL say to run `devops repos remotes` again when `gitea.url` changes.

#### Scenario: The URL changes
- **WHEN** `connect` saves a different `gitea.url`
- **THEN** the command prints the instruction to run `devops repos remotes` again

### Requirement: Connect discovers the Ingress host
`devops repos gitea connect` SHALL discover the Ingress host of `gitea-http` in namespace `gitea` when `--url` is absent.

#### Scenario: The URL comes from Ingress discovery
- **WHEN** `kubectl get ingress -A -o json` is stubbed with a `gitea-http` host
- **THEN** `connect` uses `https://<host>` and saves it as `gitea.url`

### Requirement: Connect names a missing token
`devops repos gitea connect` SHALL exit 1 and name `devops config set gitea.token` when the token is missing.

#### Scenario: The token is missing
- **WHEN** `connect` runs without a keyring token
- **THEN** the command exits 1 and names `devops config set gitea.token`

### Requirement: Connect names a missing Ingress
`devops repos gitea connect` SHALL exit 1 and name `--url` when no Ingress exists.

#### Scenario: No Gitea Ingress exists
- **WHEN** `connect` finds no Ingress host and `--url` is absent
- **THEN** the command exits 1 and names `--url`

### Requirement: Connect reports Access blocked
`devops repos gitea connect` SHALL exit 1 with the message of `GiteaAccessBlocked`.

#### Scenario: Access blocks connect
- **WHEN** `connect` gets a `GiteaAccessBlocked` error
- **THEN** the command exits 1 and prints the error message

### Requirement: Remotes ensure the organisation
`devops repos remotes` SHALL ensure the Gitea organisation exists and SHALL create it only on 404.

#### Scenario: The organisation is absent
- **WHEN** `org` returns 404
- **THEN** the client sends `POST /orgs` with `visibility: private`

### Requirement: Remotes use the user namespace
`devops repos remotes` SHALL skip organisation creation when the owner equals the token's login and SHALL create the repository under `/user/repos`.

#### Scenario: The owner is the token's login
- **WHEN** the clone's owner equals `current_user.login`
- **THEN** the client sends `POST /api/v1/user/repos` and no `POST /orgs`

### Requirement: Remotes ensure the repository
`devops repos remotes` SHALL ensure the repository exists, create it only on 404, and set `default_branch` to the clone's GitHub default branch.

#### Scenario: A repository is absent on Gitea
- **WHEN** `repo` returns 404 and `create_repo` runs
- **THEN** the client creates the repository with `private: true`, `auto_init: false` and the GitHub default branch

### Requirement: Remotes read origin HEAD
`devops repos remotes` SHALL read the clone's GitHub default branch with `git symbolic-ref --short refs/remotes/origin/HEAD` through the process runner.

#### Scenario: The default branch is read from origin/HEAD
- **WHEN** `origin/HEAD` points to `refs/remotes/origin/master`
- **THEN** the command reads `master` as the GitHub default branch

### Requirement: Remotes create protections
`devops repos remotes` SHALL create one branch protection for the GitHub default branch and each `gitea.github_branches` pattern that has no rule.

#### Scenario: A protection exists
- **WHEN** `branch_protections` already returns the rule
- **THEN** no POST creates a second rule

### Requirement: Protection settings
Each created branch protection SHALL set `rule_name` to the pattern, `enable_push: true`, `enable_force_push: false` and list-order priority.

#### Scenario: A protection is created
- **WHEN** `create_branch_protection` runs
- **THEN** the request body holds the pattern as `rule_name`, `enable_push: true`, `enable_force_push: false` and the pattern's list-order priority

### Requirement: Remotes set the remote URL
`devops repos remotes` SHALL create or update the `gitea` remote with `git remote add` or `git remote set-url` through the process runner, using `gitea.url` joined to `<owner>/<name>.git`, and SHALL leave `origin` and branch upstreams untouched.

#### Scenario: The remote URL changes
- **WHEN** `gitea.url` changes and `remotes` runs again
- **THEN** the `gitea` remote URL is updated and `origin` keeps its URL

### Requirement: Remotes set the helper entries
`devops repos remotes` SHALL set `credential.<gitea.url>.helper` in the clone's config to an empty value and then to `!devops repos gitea credential`, and SHALL not touch global git config.

#### Scenario: The helper entries are written in order
- **WHEN** `remotes` runs on a clone
- **THEN** `git config --get-all credential.<gitea.url>.helper` prints the empty entry then the `!devops` entry

### Requirement: Remotes remove old helper entries
`devops repos remotes` SHALL remove the old URL's helper entries when the URL changes.

#### Scenario: The URL changes
- **WHEN** `gitea.url` changes and `remotes` runs again
- **THEN** the old URL's `credential.<old-url>.helper` entries are removed

### Requirement: Remotes set checkout defaults
`devops repos remotes` SHALL set `checkout.defaultRemote` to `origin` and `remote.gitea.tagOpt` to `--no-tags` in the clone's config.

#### Scenario: A clone has both remotes
- **WHEN** `remotes` runs
- **THEN** the clone's config holds `checkout.defaultRemote=origin` and `remote.gitea.tagOpt=--no-tags`

### Requirement: Remotes seed the default branch
`devops repos remotes` SHALL seed the GitHub default branch and every matching origin branch with `refs/remotes/origin/<branch>:refs/heads/<branch>`.

#### Scenario: The first run seeds main
- **WHEN** the bare `gitea` repository has no `main`
- **THEN** the first run pushes `origin/main` to `gitea` `refs/heads/main`

### Requirement: Remotes use the GitHub default branch
`devops repos remotes` SHALL use the clone's GitHub default branch from `refs/remotes/origin/HEAD` and SHALL create, protect, seed and sync that branch when it is not `main`.

#### Scenario: The GitHub default branch is master
- **WHEN** the clone's `origin/HEAD` names `master`
- **THEN** `remotes` creates `master` as Gitea's default branch, protects it and seeds it

### Requirement: Remotes are idempotent
A second `devops repos remotes` run with no change SHALL make only GET calls, run no push, and print no created row.

#### Scenario: A second run changes nothing
- **WHEN** `remotes` runs twice with no change
- **THEN** the transport records only GET requests, no push runs, and the table shows no created row

### Requirement: Remotes dry run
`devops repos remotes --dry-run` SHALL print the plan per clone and SHALL make only GET calls.

#### Scenario: A dry run makes no write
- **WHEN** `remotes --dry-run` runs against a `MockTransport`
- **THEN** the transport records only GET requests and the table shows the plan

### Requirement: Remotes record extra checkouts
`devops repos remotes` SHALL cover each clone from `iter_workspace_repos`, each `gitea.extra_checkouts` entry and each `--path`, and SHALL record each resolved `--path` once in `gitea.extra_checkouts`, using `gh repo view --json owner,name` for a checkout outside `repos/`.

#### Scenario: A path outside repos is added
- **WHEN** `remotes --path /workspaces/devops-cli` runs twice
- **THEN** `gitea.extra_checkouts` holds the resolved path once and the owner and name come from `gh repo view`

### Requirement: Remotes skip standalone clones
`devops repos remotes` SHALL skip `repos/_standalone/*` with a note.

#### Scenario: A standalone clone is skipped
- **WHEN** `iter_workspace_repos` yields `repos/_standalone/tool`
- **THEN** the command prints a skip note and makes no Gitea call for it

### Requirement: Remotes report one table
`devops repos remotes` SHALL print one table with columns clone, created, protected, remote and seeded, and SHALL continue after a failed clone with exit code 1.

#### Scenario: A clone fails
- **WHEN** one clone raises `GiteaError`
- **THEN** the command reports that clone, continues with the rest, and exits 1

### Requirement: Remotes stop on Access blocked
`devops repos remotes` SHALL stop the run at the first clone when `GiteaAccessBlocked` occurs.

#### Scenario: Access blocks the first clone
- **WHEN** the first clone raises `GiteaAccessBlocked`
- **THEN** the command stops and makes no call for a later clone

### Requirement: Credential helper is hidden
The `devops repos gitea credential` command group SHALL be hidden from `--help`.

#### Scenario: The helper is hidden
- **WHEN** `devops repos gitea --help` runs
- **THEN** the output does not list `credential`

### Requirement: Credential get reads stdin
`devops repos gitea credential get` SHALL read git's `key=value` lines from stdin and print `username` and `password` only for an `https` host with any port that matches `gitea.url`.

#### Scenario: A matching host returns the token
- **WHEN** stdin holds `protocol=https` and `host=git.example.com`
- **THEN** the helper prints `username=<gitea.username>` and `password=<keyring token>`

### Requirement: Credential get ignores other hosts
`devops repos gitea credential get` SHALL print nothing for any other protocol or host.

#### Scenario: Another host gets no answer
- **WHEN** stdin holds `protocol=https` and `host=example.com`
- **THEN** the helper prints nothing

### Requirement: Credential get makes no request
`devops repos gitea credential get` SHALL make no network call.

#### Scenario: The helper reads the keyring
- **WHEN** the helper gets a matching host
- **THEN** the `MockTransport` records no request

### Requirement: Credential store and erase do nothing
`devops repos gitea credential store` and `erase` SHALL do nothing, and the token SHALL never reach argv, a log or a file.

#### Scenario: The helper starts no command with the token
- **WHEN** the credential helper runs with a recording `run_subprocess` stub
- **THEN** no argument list holds the token, the keyring is unchanged, and no output holds the token

### Requirement: Sync fetches both remotes
`devops repos sync` SHALL fetch both remotes through `fetch_all`, which raises `GitOperationError` for a failed fetch.

#### Scenario: Sync fetches origin and gitea
- **WHEN** `sync` runs on a clone with both remotes
- **THEN** the command fetches `origin` and `gitea`

### Requirement: Sync can turn the Gitea push off
`devops repos sync` SHALL push to Gitea by default and `--no-gitea` SHALL turn the push off.

#### Scenario: The Gitea push is turned off
- **WHEN** `sync --no-gitea` runs
- **THEN** the command fetches both remotes and makes no Gitea push

### Requirement: Sync pushes the default branch
`devops repos sync` SHALL push `refs/remotes/origin/<branch>:refs/heads/<branch>` for the GitHub default branch and each matching `gitea.github_branches` pattern without force.

#### Scenario: Sync carries main to Gitea
- **WHEN** `origin/main` is ahead of `gitea/main`
- **THEN** sync fast-forwards `gitea/main` and reports success

### Requirement: Sync matches branch names
`devops repos sync` SHALL match branch names with `PurePosixPath(branch).full_match(pattern)`, where `*` does not cross `/`.

#### Scenario: A nested branch does not match
- **WHEN** `gitea.github_branches` holds `release/*` and origin has `release/1/fix`
- **THEN** sync does not push `release/1/fix`

### Requirement: Sync reads porcelain results
`devops repos sync` SHALL run `git push --porcelain` through the process runner and SHALL read each branch's result from the porcelain status lines.

#### Scenario: A successful branch is read from porcelain
- **WHEN** `git push --porcelain` prints a `*` line for `main`
- **THEN** sync reports `main` as updated

### Requirement: Sync reports a rejected branch
`devops repos sync` SHALL report a rejected non-fast-forward per branch from the `!` line of `git push --porcelain` with `git log gitea/<branch> ^origin/<branch>` and SHALL continue with the next branch.

#### Scenario: A diverged main is rejected
- **WHEN** `git push --porcelain` prints `!` for `main`
- **THEN** sync reports the branch as rejected, names the inspection command, and leaves `gitea/main` unchanged

### Requirement: Sync skips a push after a failed fetch
`devops repos sync` SHALL report a failed fetch from `origin` or `gitea` and SHALL skip that clone's Gitea push.

#### Scenario: A fetch fails
- **WHEN** `fetch_all` raises for `origin` or `gitea`
- **THEN** sync reports the failure and makes no Gitea push for that clone

### Requirement: Sync never pushes an iteration branch
`devops repos sync` SHALL never push an iteration branch.

#### Scenario: An iteration branch exists on origin
- **WHEN** `origin/topic` matches no `gitea.github_branches` pattern
- **THEN** sync makes no push for `topic`

### Requirement: Clone runs the Gitea ensure step
`devops repos clone` and `clone-org` SHALL run the same Gitea ensure step for each new clone when `gitea.url` is set.

#### Scenario: A new clone gets the remote
- **WHEN** `clone` creates a clone and `gitea.url` is set
- **THEN** the clone gets the `gitea` remote and the helper entries

### Requirement: Clone keeps a Gitea failure as a warning
A Gitea failure in that step SHALL be a warning that keeps the clone.

#### Scenario: The Gitea ensure step fails after a clone
- **WHEN** `clone` creates a clone and the Gitea call raises `GiteaError`
- **THEN** the command warns and the clone remains

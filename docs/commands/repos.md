# `devops repos`

Clone, synchronize, and manage organization repositories.

## Commands

## `devops repos clone-org`

**Clone all repos from a GitHub org into `repos/<org>/.`.**

```bash
devops repos clone-org [OPTIONS] <org>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<org>` | `string` | No | GitHub organisation name. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | Base repository root directory. |
| `--private` / `--no-private` | `boolean` | `True` | - |
| `--forks` / `--no-forks` | `boolean` | - | - |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops repos clone`

**Clone an individual repository into `repos/<org>/<name>/.` (or `repos/_standalone/<name>/.`).**

```bash
devops repos clone [OPTIONS] <url>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<url>` | `string` | Yes | Repository URL (SSH or HTTPS). |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | Base repository root directory. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops repos list`

**List all cloned repositories.**

```bash
devops repos list [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |

---

## `devops repos update`

**Fetch (and optionally pull) all tracking branches across repos, and push default branches to Gitea.**

Fetch (and optionally pull) all tracking branches across repos, and push default branches to Gitea.

GitHub owns the default branch. devops repos sync carries the default branch from origin
to Gitea without force. Pass --no-gitea to skip pushing to Gitea.

```bash
devops repos update [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |
| `--pull` / `--no-pull` | `boolean` | `True` | - |
| `--no-gitea` | `boolean` | - | Do not push branches to Gitea remotes. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops repos sync`

**Fetch (and optionally pull) all tracking branches across repos, and push default branches to Gitea.**

Fetch (and optionally pull) all tracking branches across repos, and push default branches to Gitea.

GitHub owns the default branch. devops repos sync carries the default branch from origin
to Gitea without force. Pass --no-gitea to skip pushing to Gitea.

```bash
devops repos sync [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | - |
| `--pull` / `--no-pull` | `boolean` | `True` | - |
| `--no-gitea` | `boolean` | - | Do not push branches to Gitea remotes. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops repos remotes`

**Ensure Gitea remotes, organizations, repositories, protections, and default branch seeds.**

Ensure Gitea remotes, organizations, repositories, protections, and default branch seeds.

GitHub owns the default branch (main), tags, pull requests, CI, and releases. Gitea owns
iteration branches.

Setup:
1. Set the keyring token: devops config set gitea.token
2. Connect to Gitea: devops repos gitea connect
3. Configure remotes: devops repos remotes

Traffic passes Cloudflare Access through the homelab-public-ip-bypass policy.
Push iteration branches to Gitea with: git push -u gitea \<topic\>

```bash
devops repos remotes [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--base-dir`, `-d` | `path` | - | Base repository root directory. |
| `--path`, `-p` | `path` | - | Extra repository checkout path outside repos/ to configure and sync. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops repos onboard`

**Onboard one repository from the baseline of the template repository: settings, release environment, labels, template pull request, ruleset and Service. Details: docs/repos/onboard.md.**

```bash
devops repos onboard [OPTIONS] <repo>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<repo>` | `string` | No | The repository as owner/name. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--all` | `boolean` | - | Check each repository of service.repos. Takes --plan or --dry-run only. |
| `--plan` | `boolean` | - | Read and compare only: GET requests and the clone of the template. The default. |
| `--dry-run` | `boolean` | - | Send no request and start no program; list the reads and the write routes. |
| `--confirm` | `boolean` | - | Write each difference, open the template pull request and connect the Service. |
| `--create` | `boolean` | - | Create the repository of the login when it does not exist. Needs --visibility. |
| `--visibility` | `choice (public|private)` | - | The visibility of a repository that --create makes. |
| `--scope` | `string` | - | A Conventional Commit scope of the repository, for its scope/* label. Give it once for each scope. An answer: it applies before .copier-answers.yml exists. |
| `--release-flow` / `--no-release-flow` | `boolean` | - | Give the repository the release flow of release-please, or not. The default: yes. A repository that can have no environment gets none, also with this flag (D2). An answer. |
| `--release-type` | `choice (simple|python|node)` | - | The release type of release-please. An answer. |
| `--template-ref` | `string` | - | The tag of the template repository to render. The default: _commit of .copier-answers.yml, else the latest release. |
| `--release-key-file` | `path` | - | A PEM file that holds the private key of the release App. The default: the credential github.release_app_private_key. |
| `--rotate-release-key` | `boolean` | - | Seal the release key again when the environment holds it. |
| `--no-deploy` | `boolean` | - | Add the repository to service.repos, but do not run push-secrets and deploy-stack. |
| `--service` | `boolean` | - | The repository is a service: add the person step of its services entry. |
| `--only` | `string` | - | Run only these rows, as numbers separated by commas, such as 2,3,8. |

---

## `devops repos worktrees`

```bash
devops repos worktrees COMMAND [ARGS]...
```

### `devops repos worktrees status`

**List every worktree with commits ahead of main, dirty-path count, and flags.**

```bash
devops repos worktrees status [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo-dir`, `-r` | `path` | - | Repository root directory. |
| `--format`, `-f` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json` | `boolean` | - | Emit output as JSON. |

### `devops repos worktrees add`

**Create the worktree of an issue on \<type\>/\<issue\>-\<slug\> at the fetched origin/main.**

Create the worktree of an issue on \<type\>/\<issue\>-\<slug\> at the fetched origin/main.

The command reads the branches of origin before it removes the worktrees of merged pull
requests under the agent worktrees folder, as prune --confirm does, because a merged worktree
still holds its issue: a read that fails removes no worktree and leaves the HEAD of the clone as
it was. It keeps a worktree outside that folder and a worktree that holds ignored data files,
and names each; regenerable caches, such as .venv, are no data. Then it refuses an issue that a
worktree,
the standard directory or a pushed branch of origin already holds. A pushed branch whose
commits past origin/main all have the App as author is a staged branch: the command adds the
worktree on it and takes --type and --slug from it. After the worktree exists, the command
claims the issue for an agent with the label owner/agent, and sets the Status In Progress
when the item is New, Ready or Planned, or has no Status. It only warns if the claim or the
Status write fails.

```bash
devops repos worktrees add [OPTIONS] <issue>
```

**Arguments:**

| Argument | Type | Required | Description |
|---|---|---|---|
| `<issue>` | `integer` | Yes | The number of the issue that the worktree is for. |

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--type` | `string` | - | The type of the branch: a type of release-please-config.json. Needed unless origin holds a staged branch for the issue; then it must equal the type of that branch. |
| `--slug` | `string` | - | The slug of the branch: lowercase letters and digits joined by single hyphens. Needed unless origin holds a staged branch for the issue; then it must equal the slug of that branch. |
| `--title` | `string` | - | Title for the item or entity. |
| `--repo-dir`, `-r` | `path` | - | Repository root directory. |
| `--reclaim` / `--no-reclaim` | `boolean` | `True` | First remove the worktrees of merged pull requests, as prune --confirm does. --no-reclaim skips this. |
| `--dry-run`, `-n` | `boolean` | - | Preview execution plan without mutating external state. |
| `--format` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json` | `boolean` | - | Emit output as JSON. |

### `devops repos worktrees prune`

**Remove the worktrees whose tip heads a merged pull request; preview unless --confirm.**

Remove the worktrees whose tip heads a merged pull request; preview unless --confirm.

Prune removes only a clean, unlocked worktree under the managed folder (.data/agent/worktrees
by default) that holds no ignored data file. It keeps a worktree outside that folder, also a
record whose directory is missing, and a worktree that holds ignored data files, and it reads
no pull request for them. An ignored data file is a file that .gitignore hides, but the
regenerable caches and build outputs, such as .venv, .pytest_cache, dist and .data/cache,
are no data. Without --confirm it reads GitHub and removes nothing; --dry-run makes no
request. --force removes every worktree but the main worktree and the worktree that
holds the current directory, whatever its state or folder.

```bash
devops repos worktrees prune [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--repo-dir`, `-r` | `path` | - | Repository root directory. |
| `--force`, `-f` | `boolean` | - | Remove every worktree but the main worktree and the worktree that holds the current directory, whatever its state or folder. Needs --confirm. |
| `--confirm` | `boolean` | - | Remove the worktrees. Without it, prune only lists what it would remove. |
| `--dry-run`, `-n` | `boolean` | - | Preview execution plan without mutating external state. |
| `--format` | `string` | `table` | Output format type (table, json, yaml, markdown). |
| `--json` | `boolean` | - | Emit output as JSON. |

---

## `devops repos gitea`

```bash
devops repos gitea COMMAND [ARGS]...
```

### `devops repos gitea connect`

**Connect devops-cli to Gitea, verify credentials, and store settings.**

```bash
devops repos gitea connect [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--url` | `string` | - | Gitea instance HTTPS URL (defaults to discovered Ingress host). |
| `--context` | `string` | - | Kubernetes context to query for Gitea Ingress. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

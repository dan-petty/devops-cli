# renovate-service Specification

## Purpose
How self-hosted Renovate runs in namespace `devops`: the CronJob and its pinned image, the token init container that alone reads the App key, the pod controls under a read-only root, the global config, the cache claim, the network perimeter, the Secret row and the records of its license exception. Renovate runs commands that a repository names, so its pod holds no key of the Service and reaches no internal service.

## Requirements

### Requirement: The timeouts nest inside the life of the token
The `executionTimeout` of the global config, in seconds, SHALL be less than `activeDeadlineSeconds`, and `activeDeadlineSeconds` SHALL be less than 3600 s, the life of a GitHub installation token.

#### Scenario: The three values
- **WHEN** a person runs `kubectl -n devops get jobs -l app.kubernetes.io/name=renovate -o jsonpath='{..conditions[?(@.type=="Failed")].reason}'`
- **THEN** no Job failed with the reason `DeadlineExceeded`, because Renovate ends a long run at `executionTimeout` before the Job deadline, and the token stays valid for the whole run

### Requirement: Only the token init container reads Secret renovate
Init container `token` SHALL run the Service image with the args `gh app-token --app renovate --write /token/github-token`, and SHALL be the only container with `envFrom` (optional) or a `secretKeyRef`. No volume SHALL be a Secret. Container `renovate` SHALL mount the volume `token` writable, and `config.js` SHALL read `/token/github-token` into the config and remove that file before it exports the config, so a child process of user 12021 finds no token file.

#### Scenario: A container reads the Secret
- **WHEN** a person runs `kubectl get cronjob renovate -o yaml` in namespace `devops` on the cluster
- **THEN** init container `token` is the only container with `envFrom` or a `secretKeyRef`, no volume is a Secret, and container `renovate` mounts the volume `token` with no `readOnly: true`, and `uv run devops gh pr list --state all` lists the pull requests that the last run opened with the token that the init container wrote

#### Scenario: A config that keeps the token
- **WHEN** `uv run devops ci --check --only k8s` runs against a `config.js` that reads `/token/github-token` and does not remove it
- **THEN** the row exits non-zero and its message names `/token/github-token`

### Requirement: The pod meets Pod Security restricted with a read-only root
The pod SHALL run as user and group 12021 with `runAsNonRoot`, `fsGroup` 12021, the `RuntimeDefault` seccomp profile and no service account token. Each container SHALL drop all capabilities, allow no privilege escalation and have a read-only root. The volumes SHALL be ConfigMap, emptyDir and PVC volumes only.

#### Scenario: A control is missing
- **WHEN** the CronJob starts a Job in namespace `devops`, which enforces Pod Security `restricted`, and a person runs `uv run devops k8s lint k8s/devops/renovate`
- **THEN** the API server admits the pod of the Job, and Kube-linter reports no `no-read-only-root-fs`, `privilege-escalation-container`, `privileged-container` or `run-as-non-root` finding

### Requirement: Renovate writes only to volumes, and the seed keeps the image files
Container `renovate` SHALL write only to `/tmp`, `/opt/containerbase`, `/home/ubuntu`, `/cache` and `/report`. Init container `seed` SHALL run the Renovate image and copy `/opt/containerbase` and `/home/ubuntu` into one emptyDir, which `renovate` SHALL mount on the same paths with `subPath`.

#### Scenario: The writable paths
- **WHEN** a Renovate Job runs on its read-only root, and a person runs `kubectl -n devops logs <pod> -c renovate`
- **THEN** the run installs its tools and ends, and the log holds no error for a read-only file system

### Requirement: The global config scopes Renovate to the App installation and onboards no repository yet
The global config SHALL set `platform: github`, `autodiscover: true`, `onboarding: false`, `requireConfig: required` and an `onboardingConfig` that extends `github>dan-petty/devops-cli//.github/renovate/base`. It SHALL hold no `token` and no `gitAuthor` in `config.json`, and SHALL name no Mend service.

#### Scenario: A repository with no config
- **WHEN** a Renovate run reaches a repository of the App installation that holds no Renovate config, and a person runs `kubectl -n devops logs <pod> -c renovate`
- **THEN** the log says that the run skips the repository, and the repository gets no onboarding pull request

### Requirement: A post-upgrade task cannot open the installation token
A `postUpgradeTasks` command SHALL run as user 12021 in container `renovate` and SHALL open no `/token/github-token`, because `config.js` reads that file into the Renovate config and removes it before Renovate processes a repository. `allowShellExecutorForPostUpgradeCommands` SHALL stay false, and `allowedCommands` SHALL hold only an anchored regex for each command that `.github/renovate.json` names, so a command with no regex runs nowhere.

#### Scenario: A new command
- **WHEN** a person runs `kubectl get configmap renovate-config -o yaml` in namespace `devops` on the cluster
- **THEN** `allowedCommands` holds only anchored regexes and `allowShellExecutorForPostUpgradeCommands` is false, so Renovate runs no command that no regex matches and no command in a shell

#### Scenario: The token path after the config runs
- **WHEN** `uv run devops ci test tests/invariants/test_k8s_renovate.py` runs the `config.js` of ConfigMap `renovate-config` with `DEVOPS_CLI_TOKEN_FILE` at a temporary path and then starts a `node` child process that opens that path
- **THEN** the child exits non-zero with `ENOENT`, because the script removed the file before the child started

### Requirement: The caches are on a kept claim, and Renovate opens update pull requests
The config SHALL set `binarySource: install`, `cacheDir` on PVC `renovate-cache` (`local-path`, 5Gi, ReadWriteOnce, `Prune=false,Delete=false`), `containerbaseDir` under it, `repositoryCache: enabled`, `reportType: file` and `persistRepoData: false`. The container SHALL set no `RENOVATE_DRY_RUN`: the first measured run (#4909) was a lookup dry run, and Renovate now opens update pull requests.

#### Scenario: The cache and the dry run
- **WHEN** a person runs `kubectl -n devops get pvc renovate-cache` and `uv run devops gh pr list --state all`
- **THEN** the claim is `Bound`, and the list holds update pull requests that Renovate opened after its last run
- **AND** `uv run devops ci --check --only k8s` passes only when the claim has `Prune=false` and `Delete=false`

### Requirement: The Renovate pod reaches only DNS, the collector and public HTTPS
`devops-default-perimeter` SHALL skip pods with `app.kubernetes.io/name: renovate`. NetworkPolicy `renovate-perimeter` SHALL select them, admit no ingress, and allow egress to CoreDNS, the collector on TCP 4318 and public TCP 443 with the except list of `devops-default-perimeter`.

#### Scenario: A path to an internal service
- **WHEN** a throwaway pod with the label `app.kubernetes.io/name: renovate` in namespace `devops` runs `nc -w 3` to `github.com` on TCP 443, to the collector on TCP 4318, and to the gateway on TCP 4000, Valkey on TCP 6379, Qdrant on TCP 6333 and the API server on TCP 443, started with `kubectl run --rm -i --restart=Never`
- **THEN** the connects to `github.com` and to the collector succeed, and each connect to the gateway, Valkey, Qdrant and the API server times out

### Requirement: The Secret row holds the two IDs and the key under their variables
The cluster secret table SHALL hold `devops/renovate`, an optional-feature Secret in stack `devops` with no restart, and three optional keys: the variables of `renovate.github_app_id` and `renovate.github_app_installation_id` from their settings, and of `renovate.github_app_private_key` from its keyring entry. The token container SHALL take it as optional. The `homelab` AppProject SHALL ignore Secret `renovate`.

#### Scenario: The push
- **WHEN** a person runs `uv run devops k8s push-secrets --stack devops --dry-run` and `kubectl -n argocd get applications -o jsonpath='{..conditions[*].type}'`
- **THEN** the dry run writes Secret `devops/renovate` with the keys `DEVOPS_CLI_RENOVATE_GITHUB_APP_ID`, `DEVOPS_CLI_RENOVATE_GITHUB_APP_INSTALLATION_ID` and `DEVOPS_CLI_RENOVATE_GITHUB_APP_PRIVATE_KEY` and no restart, with no value in the output
- **AND** no Application of project `homelab` has the condition `OrphanedResourceWarning` for Secret `renovate`

#### Scenario: A workstation with no Renovate settings
- **WHEN** `devops k8s push-secrets --stack devops` runs with no Renovate setting and no keyring entry
- **THEN** the push skips the three keys with a warning, writes no Secret `renovate`, and exits 0

### Requirement: A security fix of this repository merges itself after the required checks
The `vulnerabilityAlerts` object of `.github/renovate.json` SHALL set `automerge: true`, `automergeType: pr` and `platformAutomerge: true`, for each update type, so GitHub merges a security fix only after the required checks of the ruleset `main` pass. No other part of `.github/renovate.json` and no part of `.github/renovate/base.json` SHALL turn automerge on.

#### Scenario: The automerge scope
- **WHEN** Renovate opens a pull request for a security alert and a pull request for another update, and a person runs `uv run devops gh pr view <number>` for each
- **THEN** GitHub auto-merge is on for the security fix and off for the other update, and the security fix merges only after the required checks of the ruleset `main` pass

### Requirement: The CronJob runs Renovate every 2 hours, one run at a time
CronJob `renovate` in `k8s/devops/renovate/cronjob.yaml` SHALL run `ghcr.io/renovatebot/renovate:<release>@sha256:<digest>` with the command `/usr/local/sbin/renovate-entrypoint.sh` and the args `renovate`, on the schedule `17 */2 * * *` in `Etc/UTC`, with `concurrencyPolicy: Forbid`, `startingDeadlineSeconds: 600`, `backoffLimit: 0`, `ttlSecondsAfterFinished: 86400` and `activeDeadlineSeconds: 3000`.

#### Scenario: The image and the schedule
- **WHEN** a person runs `uv run devops k8s image-pins k8s/devops` and `kubectl -n devops get cronjob renovate`
- **THEN** the command resolves the Renovate image by its digest at the registry, and the CronJob is not suspended and was last scheduled less than 2 hours ago

#### Scenario: One run at a time
- **WHEN** a run is still active at the next minute of the schedule, and a person runs `kubectl -n devops get jobs -l app.kubernetes.io/name=renovate`
- **THEN** one Job is active, and the CronJob starts no second Job

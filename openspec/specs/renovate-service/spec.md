# renovate-service Specification

## Purpose
How self-hosted Renovate runs in namespace `devops`: the CronJob and its pinned image, the token init container that alone reads the App key, the pod controls under a read-only root, the global config, the cache claim, the network perimeter, the Secret row and the records of its license exception. Renovate runs commands that a repository names, so its pod holds no key of the Service and reaches no internal service.

## Requirements

### Requirement: The CronJob runs the pinned Renovate release every 2 hours, one run at a time
CronJob `renovate` in `k8s/devops/renovate/cronjob.yaml` SHALL run `ghcr.io/renovatebot/renovate:<release>@sha256:<digest>` with the command `/usr/local/sbin/renovate-entrypoint.sh` and the args `renovate`, on the schedule `17 */2 * * *` in `Etc/UTC`, with `concurrencyPolicy: Forbid`, `startingDeadlineSeconds: 600`, `backoffLimit: 0`, `ttlSecondsAfterFinished: 86400` and `activeDeadlineSeconds: 3000`.

#### Scenario: A test reads the CronJob
- **WHEN** a test reads CronJob `renovate`
- **THEN** the image holds a release tag and a 64-digit digest, and each value above is set

### Requirement: The timeouts nest inside the life of the token
The `executionTimeout` of the global config, in seconds, SHALL be less than `activeDeadlineSeconds`, and `activeDeadlineSeconds` SHALL be less than 3600 s, the life of a GitHub installation token.

#### Scenario: The three values
- **WHEN** a test reads `executionTimeout` (15 minutes) and the Job deadline (3000 s)
- **THEN** 900 < 3000 < 3600

### Requirement: Only the token init container reads Secret renovate
Init container `token` SHALL run the Service image with the args `gh app-token --app renovate --write /token/github-token`, and SHALL be the only container with `envFrom` (optional) or a `secretKeyRef`. No volume SHALL be a Secret. Container `renovate` SHALL mount the volume `token` read-only, and `config.js` SHALL read `/token/github-token`.

#### Scenario: A container reads the Secret
- **WHEN** a test reads the env and the volumes of each container
- **THEN** only `token` takes Secret `renovate`, and the token path is outside the system folders that the writer refuses

### Requirement: The pod meets Pod Security restricted with a read-only root
The pod SHALL run as user and group 12021 with `runAsNonRoot`, `fsGroup` 12021, the `RuntimeDefault` seccomp profile and no service account token. Each container SHALL drop all capabilities, allow no privilege escalation and have a read-only root. The volumes SHALL be ConfigMap, emptyDir and PVC volumes only.

#### Scenario: A control is missing
- **WHEN** a test reads the pod spec of CronJob `renovate`
- **THEN** each control above is set for the pod and for `seed`, `token` and `renovate`

### Requirement: Renovate writes only to volumes, and the seed keeps the image files
Container `renovate` SHALL write only to `/tmp`, `/opt/containerbase`, `/home/ubuntu`, `/cache` and `/report`. Init container `seed` SHALL run the Renovate image and copy `/opt/containerbase` and `/home/ubuntu` into one emptyDir, which `renovate` SHALL mount on the same paths with `subPath`.

#### Scenario: The writable paths
- **WHEN** a test reads the volume mounts of `seed` and `renovate`
- **THEN** the seed command is `cp -a --no-preserve=ownership --parents /opt/containerbase /home/ubuntu <mount>`, and the writable paths of `renovate` are the five above

### Requirement: The global config scopes Renovate to the App installation and onboards no repository yet
The global config SHALL set `platform: github`, `autodiscover: true`, `onboarding: false`, `requireConfig: required` and an `onboardingConfig` that extends `github>dan-petty/devops-cli//.github/renovate/base`. It SHALL hold no `token` and no `gitAuthor` in `config.json`, and SHALL name no Mend service.

#### Scenario: A repository with no config
- **WHEN** a test reads `config.json` of ConfigMap `renovate-config`
- **THEN** each value above is set, so a repository without a Renovate config gets no onboarding pull request

### Requirement: No upgrade task runs until the token is out of its reach
A `postUpgradeTasks` command runs in the container that can read the installation token (#6020). Until #6020 keeps the token away from the tasks, `allowedCommands` SHALL be empty, the Renovate config of this repository SHALL name no `postUpgradeTasks`, and `allowShellExecutorForPostUpgradeCommands` SHALL be false. A group that needs a task SHALL name its commands in `prBodyNotes`.

#### Scenario: A new command
- **WHEN** a pull request adds a `postUpgradeTasks` command or an `allowedCommands` regex before #6020
- **THEN** the test fails and names the command

### Requirement: The caches are on a kept claim, and Renovate opens update pull requests
The config SHALL set `binarySource: install`, `cacheDir` on PVC `renovate-cache` (`local-path`, 5Gi, ReadWriteOnce, `Prune=false,Delete=false`), `containerbaseDir` under it, `repositoryCache: enabled`, `reportType: file` and `persistRepoData: false`. The container SHALL set no `RENOVATE_DRY_RUN`: the first measured run (#4909) was a lookup dry run, and Renovate now opens update pull requests.

#### Scenario: The cache and the dry run
- **WHEN** a test reads the config, the PVC and the env of `renovate`
- **THEN** each value above is set, and the env has no `RENOVATE_DRY_RUN`

### Requirement: The Renovate pod reaches only DNS, the collector and public HTTPS
`devops-default-perimeter` SHALL skip pods with `app.kubernetes.io/name: renovate`. NetworkPolicy `renovate-perimeter` SHALL select them, admit no ingress, and allow egress to CoreDNS, the collector on TCP 4318 and public TCP 443 with the except list of `devops-default-perimeter`.

#### Scenario: A path to an internal service
- **WHEN** a test reads the two policies
- **THEN** the egress rules of `renovate-perimeter` are exactly the three above, and no rule reaches the gateway, Valkey, Qdrant or the API server

### Requirement: The Secret row holds the two IDs and the key under their variables
The cluster secret table SHALL hold `devops/renovate`, an optional-feature Secret in stack `devops` with no restart, and three optional keys: the variables of `renovate.github_app_id` and `renovate.github_app_installation_id` from their settings, and of `renovate.github_app_private_key` from its keyring entry. The token container SHALL take it as optional. The `homelab` AppProject SHALL ignore Secret `renovate`.

#### Scenario: The push
- **WHEN** a test reads the row and the orphan list
- **THEN** the keys are `DEVOPS_CLI_RENOVATE_GITHUB_APP_ID`, `DEVOPS_CLI_RENOVATE_GITHUB_APP_INSTALLATION_ID` and `DEVOPS_CLI_RENOVATE_GITHUB_APP_PRIVATE_KEY`, and the orphan list names Secret `renovate`

#### Scenario: A workstation with no Renovate settings
- **WHEN** `devops k8s push-secrets --stack devops` runs with no Renovate setting and no keyring entry
- **THEN** the push skips the three keys with a warning, writes no Secret `renovate`, and exits 0

### Requirement: The license records name one exception
ADR 0027, the open-tools rule of `CONTRIBUTING.md` and the Renovate section of `docs/CLUSTER.md` SHALL each state that Renovate is AGPL-3.0-only, that only the unmodified image runs, and that a patch is a new decision. `CONTRIBUTING.md` and `docs/CLUSTER.md` SHALL link the record.

#### Scenario: One record differs
- **WHEN** a test reads the lines that name Renovate and AGPL-3.0-only in the three files
- **THEN** each file states the three points, and the two documents link ADR 0027

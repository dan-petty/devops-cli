## MODIFIED Requirements

### Requirement: The timeouts nest inside the life of the token
The `executionTimeout` of the global config, in seconds, SHALL be less than `activeDeadlineSeconds`, and `activeDeadlineSeconds` SHALL be less than 3600 s, the life of a GitHub installation token.

#### Scenario: The three values
- **WHEN** a person runs `kubectl -n devops get configmap renovate-config -o yaml` and `kubectl -n devops get cronjob renovate -o yaml` on the cluster
- **THEN** `executionTimeout` in seconds is less than `activeDeadlineSeconds`, and `activeDeadlineSeconds` is less than 3600

### Requirement: Only the token init container reads Secret renovate
Init container `token` SHALL run the Service image with the args `gh app-token --app renovate --write /token/github-token`, and SHALL be the only container with `envFrom` (optional) or a `secretKeyRef`. No volume SHALL be a Secret. Container `renovate` SHALL mount the volume `token` read-only, and `config.js` SHALL read `/token/github-token`.

#### Scenario: A container reads the Secret
- **WHEN** a person runs `kubectl -n devops get cronjob renovate -o yaml` on the cluster
- **THEN** only `token` takes Secret `renovate`, and the token path is outside the system folders that the writer refuses

### Requirement: The pod meets Pod Security restricted with a read-only root
The pod SHALL run as user and group 12021 with `runAsNonRoot`, `fsGroup` 12021, the `RuntimeDefault` seccomp profile and no service account token. Each container SHALL drop all capabilities, allow no privilege escalation and have a read-only root. The volumes SHALL be ConfigMap, emptyDir and PVC volumes only.

#### Scenario: A control is missing
- **WHEN** `uv run devops k8s lint k8s/devops/renovate` runs kube-linter on the manifests, and a Job of CronJob `renovate` starts
- **THEN** kube-linter reports no finding for the pod, and the API server admits the pod in its namespace, which enforces Pod Security `restricted`

### Requirement: The global config scopes Renovate to the App installation and onboards no repository yet
The global config SHALL set `platform: github`, `autodiscover: true`, `onboarding: false`, `requireConfig: required` and an `onboardingConfig` that extends `github>dan-petty/devops-cli//.github/renovate/base`. It SHALL hold no `token` and no `gitAuthor` in `config.json`, and SHALL name no Mend service.

#### Scenario: A repository with no config
- **WHEN** a run of CronJob `renovate` reads a repository of the installation with no Renovate config
- **THEN** Renovate opens no onboarding pull request in it

### Requirement: No upgrade task runs until the token is out of its reach
A `postUpgradeTasks` command runs in the container that can read the installation token (#6020). Until #6020 keeps the token away from the tasks, `allowedCommands` SHALL be empty, the Renovate config of this repository SHALL name no `postUpgradeTasks`, and `allowShellExecutorForPostUpgradeCommands` SHALL be false. A group that needs a task SHALL name its commands in `prBodyNotes`.

#### Scenario: A new command
- **WHEN** a person runs `kubectl -n devops get configmap renovate-config -o yaml` on the cluster before #6020
- **THEN** `allowedCommands` is empty, so Renovate runs no `postUpgradeTasks` command

### Requirement: The Renovate pod reaches only DNS, the collector and public HTTPS
`devops-default-perimeter` SHALL skip pods with `app.kubernetes.io/name: renovate`. NetworkPolicy `renovate-perimeter` SHALL select them, admit no ingress, and allow egress to CoreDNS, the collector on TCP 4318 and public TCP 443 with the except list of `devops-default-perimeter`.

#### Scenario: A path to an internal service
- **WHEN** a person runs `kubectl -n devops get networkpolicy renovate-perimeter devops-default-perimeter -o yaml` on the cluster
- **THEN** the egress rules of `renovate-perimeter` are exactly the three above, and no rule reaches the gateway, Valkey, Qdrant or the API server

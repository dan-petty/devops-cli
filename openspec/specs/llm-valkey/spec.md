# llm-valkey Specification

## Purpose
The Valkey servers of the llm namespace in the cluster manifests: the cache Valkey that holds Open WebUI's state and the run index that workstations share. It says how much memory each one keeps as data and what each one does when its data reaches that bound.

## Requirements

### Requirement: The cache Valkey and the run index refuse writes at a memory bound below their container limits
The valkey container of the Deployments `valkey` and `valkey-runs` in `k8s/llm/` SHALL start valkey-server with `--maxmemory` at most three quarters of the container's memory limit, and with `--maxmemory-policy noeviction`, so that Valkey refuses writes at the bound and evicts no key.

#### Scenario: The cache Valkey keeps at most 1536 MiB of data
- **WHEN** the Deployment `valkey` is read from `k8s/llm/valkey.yaml`
- **THEN** its valkey container starts valkey-server with `--maxmemory 1536mb` and `--maxmemory-policy noeviction`, and 1536 MiB is at most three quarters of the container's 2048Mi memory limit

#### Scenario: The run index keeps at most 512 MiB of data
- **WHEN** the Deployment `valkey-runs` is read from `k8s/llm/valkey-runs.yaml`
- **THEN** its valkey container starts valkey-server with `--maxmemory 512mb` and `--maxmemory-policy noeviction`, and 512 MiB is at most three quarters of the container's 768Mi memory limit

### Requirement: devops-cli's cache Valkey evicts the least recently used key at a bound below its container limit
The valkey container of the Deployment `valkey-devops` in `k8s/llm/valkey-devops.yaml` SHALL start valkey-server with `--maxmemory` at most three quarters of the container's memory limit, `--maxmemory-policy allkeys-lru`, `--save ""` and `--appendonly no`.

#### Scenario: The devops cache Valkey evicts at its bound
- **WHEN** the Deployment `valkey-devops` is read from `k8s/llm/valkey-devops.yaml`
- **THEN** its valkey container starts valkey-server with `--maxmemory-policy allkeys-lru`, `--save ""` and `--appendonly no`, and its `--maxmemory` is at most three quarters of the container's memory limit

### Requirement: devops-cli's cache Valkey requires its password and admits only namespace devops
The valkey container and the redis-exporter container of `valkey-devops` SHALL read the password from key `password` of Secret `valkey-devops-auth`, and the valkey container SHALL write it to a config file on a memory volume. The policy `valkey-devops-perimeter` SHALL admit namespace `devops` on TCP 6379 and namespace `monitoring` on TCP 9121, and SHALL allow no egress.

#### Scenario: The devops cache Valkey's password and perimeter
- **WHEN** `k8s/llm/valkey-devops.yaml` is read
- **THEN** both containers read `VALKEY_PASSWORD` or `REDIS_PASSWORD` from `valkey-devops-auth` key `password`, and `valkey-devops-perimeter` admits exactly namespace `devops` on 6379 and namespace `monitoring` on 9121, with no egress

### Requirement: The cluster jobs name devops-cli's cache Valkey and send its password
The devops ConfigMap template SHALL set `valkey.url` to `valkey://valkey-devops.llm.svc.cluster.local:6379/0` and hold no password. Secret `devops/devops-cli` SHALL carry `DEVOPS_CLI_VALKEY_PASSWORD` from the same keyring entry as `llm/valkey-devops-auth`, adopted from the live `llm/valkey-devops-auth password` when the keyring lacks it.

#### Scenario: The ConfigMap and the Secret name the devops cache Valkey
- **WHEN** `k8s/devops/configmap.example.yaml` and the cluster secret table are read
- **THEN** the config's `valkey` section is exactly the URL of `valkey-devops`, no key of the config names a password, and the `devops/devops-cli` entry `DEVOPS_CLI_VALKEY_PASSWORD` has the keyring source of `llm/valkey-devops-auth` and adopts from `llm/valkey-devops-auth password`

### Requirement: A Valkey cache keeps intake's embeddings across runs
When the embedder of intake has a Valkey tier, a run that starts with an empty memory cache SHALL send no embedding request for a text whose embedding an earlier run stored there.

#### Scenario: A second run over settled items
- **WHEN** two intake plan runs over the same two items and the same candidate each use a new `EmbeddingsEngine` on one shared Valkey
- **THEN** the first run sends one `/v1/embeddings` request and the second sends none

#### Scenario: No Valkey tier
- **WHEN** the same two runs use embedders with no Valkey tier
- **THEN** each run sends one `/v1/embeddings` request

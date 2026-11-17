## MODIFIED Requirements

### Requirement: The cache Valkey and the run index refuse writes at a memory bound below their container limits
The valkey container of the Deployments `valkey` and `valkey-runs` in `k8s/llm/` SHALL start valkey-server with `--maxmemory` at most three quarters of the container's memory limit, and with `--maxmemory-policy noeviction`, so that Valkey refuses writes at the bound and evicts no key.

#### Scenario: The cache Valkey keeps at most 1536 MiB of data
- **WHEN** a person runs `kubectl -n llm get deployment valkey -o jsonpath='{.spec.template.spec.containers[*].command}{.spec.template.spec.containers[*].resources.limits.memory}'` on the cluster
- **THEN** its valkey container starts valkey-server with `--maxmemory 1536mb` and `--maxmemory-policy noeviction`, and 1536 MiB is at most three quarters of the container's 2048Mi memory limit

#### Scenario: The run index keeps at most 512 MiB of data
- **WHEN** a person runs `kubectl -n llm get deployment valkey-runs -o jsonpath='{.spec.template.spec.containers[*].command}{.spec.template.spec.containers[*].resources.limits.memory}'` on the cluster
- **THEN** its valkey container starts valkey-server with `--maxmemory 512mb` and `--maxmemory-policy noeviction`, and 512 MiB is at most three quarters of the container's 768Mi memory limit

### Requirement: devops-cli's cache Valkey evicts the least recently used key at a bound below its container limit
The valkey container of the Deployment `valkey-devops` in `k8s/llm/valkey-devops.yaml` SHALL start valkey-server with `--maxmemory` at most three quarters of the container's memory limit, `--maxmemory-policy allkeys-lru`, `--save ""` and `--appendonly no`.

#### Scenario: The devops cache Valkey evicts at its bound
- **WHEN** a person runs `kubectl -n llm get deployment valkey-devops -o jsonpath='{.spec.template.spec.containers[*].command}{.spec.template.spec.containers[*].resources.limits.memory}'` on the cluster
- **THEN** its valkey container starts valkey-server with `--maxmemory-policy allkeys-lru`, `--save ""` and `--appendonly no`, and its `--maxmemory` is at most three quarters of the container's memory limit

### Requirement: devops-cli's cache Valkey requires its password and admits only namespace devops
The valkey container and the redis-exporter container of `valkey-devops` SHALL read the password from key `password` of Secret `valkey-devops-auth`, and the valkey container SHALL write it to a config file on a memory volume. The policy `valkey-devops-perimeter` SHALL admit namespace `devops` on TCP 6379 and namespace `monitoring` on TCP 9121, and SHALL allow no egress.

#### Scenario: The devops cache Valkey's password and perimeter
- **WHEN** a person runs `kubectl -n llm get deployment valkey-devops -o yaml` and `kubectl -n llm get networkpolicy valkey-devops-perimeter -o yaml` on the cluster
- **THEN** both containers read `VALKEY_PASSWORD` or `REDIS_PASSWORD` from `valkey-devops-auth` key `password`, and `valkey-devops-perimeter` admits exactly namespace `devops` on 6379 and namespace `monitoring` on 9121, with no egress

### Requirement: The cluster jobs name devops-cli's cache Valkey and send its password
The devops ConfigMap template SHALL set `valkey.url` to `valkey://valkey-devops.llm.svc.cluster.local:6379/0` and hold no password. Secret `devops/devops-cli` SHALL carry `DEVOPS_CLI_VALKEY_PASSWORD` from the same keyring entry as `llm/valkey-devops-auth`, adopted from the live `llm/valkey-devops-auth password` when the keyring lacks it.

#### Scenario: The ConfigMap and the Secret name the devops cache Valkey
- **WHEN** a person runs `kubectl -n devops get configmap devops-cli-config -o yaml` after `uv run devops k8s deploy-stack --stack devops`, and a runner Job reads the cache
- **THEN** the config's `valkey` section is the URL of `valkey-devops`, it names no password, and the Job reaches the cache with `DEVOPS_CLI_VALKEY_PASSWORD`

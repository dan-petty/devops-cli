# llm-valkey Specification

## Purpose
The Valkey servers of the llm namespace in the cluster manifests: the cache Valkey that holds Open WebUI's state and the run index that workstations share. It says how much memory each one keeps as data and what each one does when its data reaches that bound.

## Requirements

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
The valkey container of `valkey-devops` SHALL read its users from the aclfile at `/run/valkey/users.acl`, mounted from key `users.acl` of Secret `valkey-devops-auth`. The redis-exporter container SHALL send `REDIS_USER=metrics` and key `metrics` of that Secret as `REDIS_PASSWORD`. The policy `valkey-devops-perimeter-ingress` SHALL admit namespace `devops` on TCP 6379 and namespace `monitoring` on TCP 9121, and the policy `valkey-devops-perimeter-egress` SHALL allow no egress.

#### Scenario: The devops cache Valkey's password and perimeter
- **WHEN** A person runs `kubectl -n llm get deployment valkey-devops -o yaml` and `kubectl -n llm get networkpolicy valkey-devops-perimeter-ingress valkey-devops-perimeter-egress -o yaml` on the cluster
- **THEN** The valkey container mounts key `users.acl` of `valkey-devops-auth` at `/run/valkey` and starts with `--aclfile /run/valkey/users.acl`, the exporter sets `REDIS_USER` to `metrics` and reads key `metrics`, the ingress policy admits exactly namespace `devops` on 6379 and namespace `monitoring` on 9121, and the egress policy has no egress rule

### Requirement: The cluster jobs name devops-cli's cache Valkey and send its password
The devops ConfigMap template SHALL set `valkey.url` to `valkey://valkey-devops.llm.svc.cluster.local:6379/0` and hold no password. Secret `devops/devops-cli` SHALL carry `DEVOPS_CLI_VALKEY_PASSWORD` from the same keyring entry as `llm/valkey-devops-auth`, adopted from the live `llm/valkey-devops-auth password` when the keyring lacks it.

#### Scenario: The ConfigMap and the Secret name the devops cache Valkey
- **WHEN** a person runs `kubectl -n devops get configmap devops-cli-config -o yaml` after `uv run devops k8s deploy-stack --stack devops`, and a runner Job reads the cache
- **THEN** the config's `valkey` section is the URL of `valkey-devops`, it names no password, and the Job reaches the cache with `DEVOPS_CLI_VALKEY_PASSWORD`

### Requirement: A Valkey cache keeps intake's embeddings across runs
When the embedder of intake has a Valkey tier, a run that starts with an empty memory cache SHALL send no embedding request for a text whose embedding an earlier run stored there.

#### Scenario: A second run over settled items
- **WHEN** two intake plan runs over the same two items and the same candidate each use a new `EmbeddingsEngine` on one shared Valkey
- **THEN** the first run sends one `/v1/embeddings` request and the second sends none

#### Scenario: No Valkey tier
- **WHEN** the same two runs use embedders with no Valkey tier
- **THEN** each run sends one `/v1/embeddings` request

### Requirement: A Valkey that refuses writes at its bound alerts before it reaches it
The Prometheus server SHALL fire `ValkeyMemoryNearBound` with the severity `warning` for each Valkey whose exporter reports the policy `noeviction`, a `maxmemory` above 0, and used memory above 80% of `maxmemory` for 10 minutes. The alert SHALL keep the namespace, job and instance of the exporter.

#### Scenario: The cache Valkey at 90% of its bound
- **WHEN** the `valkey-memory` group is evaluated over a Valkey with the policy `noeviction`, a `maxmemory` of 1000 bytes and 900 bytes used
- **THEN** at 5 minutes no alert fires
- **AND** at 15 minutes `ValkeyMemoryNearBound` fires with its namespace, job and instance, and the summary names 90%

#### Scenario: A Valkey under the threshold, an evicting Valkey and a Valkey with no bound
- **WHEN** a `noeviction` Valkey uses 500 of 1000 bytes, an `allkeys-lru` Valkey uses 950 of 1000 bytes, and a `noeviction` Valkey has a `maxmemory` of 0
- **THEN** `ValkeyMemoryNearBound` does not fire at 15 minutes

### Requirement: The valkey-devops pod loads its ACL users from a Secret
The valkey container of `valkey-devops` SHALL start `valkey-server` with `--aclfile /run/valkey/users.acl`, mounted read-only from key `users.acl` of Secret `valkey-devops-auth`. The aclfile SHALL keep the `default` user on with the password of key `password` of that Secret, and SHALL define the users `sweep`, `brain`, `agent` and `metrics`, each with a password of its own.

#### Scenario: Rendered aclfile
- **WHEN** A person runs `uv run devops k8s push-secrets --only llm/valkey-devops-auth` from the branch before the merge, restarts the pod with `kubectl -n llm rollout restart deploy/valkey-devops`, and reads `kubectl -n llm exec deploy/valkey-devops -c valkey -- cat /run/valkey/users.acl`
- **THEN** The file holds `user default on` and one `user <name> on` line for each of `sweep`, `brain`, `agent` and `metrics`, and no other user line

### Requirement: Each valkey-devops role user holds the key patterns of its role
The `sweep` user SHALL hold `~valkey:roadmap:*` and `~valkey:gh:*`. The `brain` user SHALL hold `~valkey:brain:*` and `%R~valkey:roadmap:*`. The `agent` user SHALL hold `~valkey:rag:*` and `%R~valkey:brain:v1:fact:*`. The `metrics` user SHALL hold no key pattern and no write command. The `agent` user SHALL receive `NOPERM` on a `valkey:roadmap:*` key.

#### Scenario: Agent key patterns
- **WHEN** A person runs `kubectl -n llm exec deploy/valkey-devops -c valkey -- sh -c "grep '^user agent ' /run/valkey/users.acl | sed -E 's/>[^ ]+/>***/'"`
- **THEN** The line holds `~valkey:rag:*` and `%R~valkey:brain:v1:fact:*`, and no pattern that matches `valkey:roadmap:*`

#### Scenario: Agent refuses a roadmap key
- **WHEN** A person runs `kubectl -n llm exec deploy/valkey-devops -c valkey -- valkey-cli --user agent --pass "$AGENT_PASSWORD" --no-auth-warning GET valkey:roadmap:probe` with the `agent` password of Secret `llm/valkey-devops-auth`
- **THEN** The command prints an error that starts with `NOPERM` and reads no value

#### Scenario: Metrics user line
- **WHEN** A person runs `kubectl -n llm exec deploy/valkey-devops -c valkey -- sh -c "grep '^user metrics ' /run/valkey/users.acl"`
- **THEN** The line holds `+info`, `+config|get`, `+dbsize`, `+client|list`, `+slowlog|get`, `+memory|usage` and `+ping`, and holds no `+@write`, no `+@all` and no `~` key pattern

### Requirement: The k8s row rejects a Valkey bound above three quarters of its memory limit
The `k8s` gate row SHALL inspect every container running `valkey-server` across rendered environment kustomizations and report a finding naming the container, its `--maxmemory` bound, and its memory limit whenever `--maxmemory` (with `kb`/`mb`/`gb` parsed as `1024`-based bytes) exceeds three quarters of `resources.limits.memory`, while ignoring `valkey-server` containers with no `--maxmemory`.

#### Scenario: A bound above three quarters fails and exact three quarters or unbound pass
- **WHEN** `uv run devops ci --check --only k8s` runs over `tests/gate/k8s_checks/valkey_memory.py`
- **THEN** a rendered Deployment whose `valkey` container sets `--maxmemory 512mb` and limit `512Mi` produces one finding naming `valkey`, `512mb`, and `512Mi`, whereas `--maxmemory 768mb` with `1Gi` and `valkey-server` without `--maxmemory` produce zero findings and the committed tree passes

# llm-valkey Specification

## Purpose
What devops-cli does with its cache Valkey `valkey-devops` of the llm namespace: the setting and the Secret that name it, the embedding cache of intake, and the ACL users that push-secrets builds. The Valkey manifests are in the environment tree of the cluster.

## Requirements

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

### Requirement: The valkey-devops pod loads its ACL users from a Secret
The push of Secret `llm/valkey-devops-auth` SHALL build the aclfile of key `users.acl`. The aclfile SHALL keep the `default` user on with the password of key `password` of that Secret, and SHALL define the users `sweep`, `brain`, `agent` and `metrics`, each with a password of its own.

#### Scenario: Rendered aclfile
- **WHEN** a test plans `llm/valkey-devops-auth` with an empty keyring
- **THEN** the planned `users.acl` holds `user default on` and one `user <name> on` line for each of `sweep`, `brain`, `agent` and `metrics`, and no other user line

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

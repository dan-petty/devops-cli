## Purpose
The Valkey store `valkey-roadmap` of namespace `devops`, which holds the shared state of the roadmap jobs (ADR 0021 section 3): the instance that the product base builds from the shared Valkey base, its settings, its network policies, its ACL users and the Secret row that gives their passwords and the aclfile.

## ADDED Requirements

### Requirement: The product base builds valkey-roadmap from the shared Valkey base
The folder `k8s/devops/valkey-roadmap` SHALL build the Valkey base of dan-petty/infra with the components `valkey-persistence`, `valkey-exporter` and `valkey-acl`, each pinned at the same release tag with `?ref=`. The repository SHALL hold no copy of the base and no Deployment of the store. `k8s/devops/kustomization.yaml` SHALL list the folder, and the build SHALL hold a Deployment and a Service with the name `valkey-roadmap` in namespace `devops`.

#### Scenario: The build of the product base
- **WHEN** a person runs `uv run devops ci --check --only k8s`
- **THEN** the row builds `k8s/devops` and `k8s/overlays/homelab/devops` with the folder `valkey-roadmap`, and passes

#### Scenario: The images of the store resolve
- **WHEN** a person runs `uv run devops k8s image-pins k8s/devops/valkey-roadmap`
- **THEN** the command resolves the image of Valkey and the image of the exporter in their registries, and exits 0

### Requirement: valkey-roadmap keeps its data on disk and evicts no key
The settings of the store SHALL set `appendonly yes`, `appendfsync everysec` and `maxmemory-policy noeviction`. The claim of the store SHALL request 2Gi of the storage class `local-path`, and the pod SHALL have the required node affinity that keeps it off a control-plane node.

#### Scenario: The live settings
- **WHEN** after the merge a person runs `kubectl -n devops exec deploy/valkey-roadmap -c valkey -- valkey-cli --user metrics --pass <password> --no-auth-warning CONFIG GET maxmemory-policy` with the password of key `metrics` of Secret `devops/valkey-roadmap-auth`
- **THEN** the command prints `noeviction`, and `kubectl -n devops get pvc valkey-data-roadmap` shows a bound claim of 2Gi

### Requirement: Only labelled pods of namespace devops reach valkey-roadmap
The network policies of the store SHALL admit to TCP 6379 only the pods of namespace `devops` with the label `valkey-client: "true"`, and to TCP 9121 only the pods of namespace `monitoring`. The pod of the store SHALL get no egress: `devops-default-perimeter-ingress` and `devops-default-perimeter-egress` SHALL NOT select a pod with the label `app.kubernetes.io/name: valkey`.

#### Scenario: The policies of the build
- **WHEN** a person runs `uv run devops ci --check --only k8s,kube-linter`
- **THEN** both rows pass: each policy of the build has one type, and a policy selects the pod of the store

#### Scenario: A pod of another namespace
- **WHEN** after the merge a person starts a pod in a namespace other than `devops` and connects to `valkey-roadmap.devops.svc.cluster.local` on TCP 6379
- **THEN** the connection gets no answer

### Requirement: The default user of valkey-roadmap is off and each user holds the keys of its role
The aclfile of the store SHALL hold `user default off`. The user `brain` SHALL hold `~roadmap:v1:brain-*` with `+@all -@dangerous`. The user `agent` SHALL hold `%R~roadmap:v1:brain-*` with `+@read +@connection -@dangerous`, so it writes no key. The user `metrics` SHALL hold no key pattern and only the commands `info`, `config|get`, `latency|latest`, `latency|histogram`, `slowlog|len`, `slowlog|get`, `commandlog|len`, `command|info` and `client|setname`. The aclfile SHALL hold no other user.

#### Scenario: The aclfile of a plan
- **WHEN** a test plans the push of `devops/valkey-roadmap-auth` on the fake cluster with an empty keyring
- **THEN** the lines of `users.acl` are `user default off` and one `user <name> on` line for each of `brain`, `agent` and `metrics` with the patterns and the commands above, in this order

#### Scenario: A connection with no user
- **WHEN** after the merge a person runs `kubectl -n devops exec deploy/valkey-roadmap -c valkey -- valkey-cli ping`
- **THEN** the command prints `NOAUTH Authentication required.`

#### Scenario: The agent user writes no key
- **WHEN** after the merge a person runs `kubectl -n devops exec deploy/valkey-roadmap -c valkey -- valkey-cli --user agent --pass <password> --no-auth-warning HSET roadmap:v1:brain-item:probe f v` with the password of key `agent`
- **THEN** the command prints an error that starts with `NOPERM`

### Requirement: The passwords and the aclfile of valkey-roadmap come from one push
The Secret table SHALL hold the row `devops/valkey-roadmap-auth` of the stack `devops` with one generated entry of 32 random bytes in hex for each of `brain`, `agent` and `metrics`, and the derived entry `users.acl` that is built from these three values in the same push. A change of the Secret SHALL restart `deployment/valkey-roadmap`. No value SHALL be in git or in the output.

#### Scenario: The generated passwords
- **WHEN** a test plans the push of `devops/valkey-roadmap-auth` on the fake cluster with an empty keyring
- **THEN** the plan holds the keys `brain`, `agent`, `metrics` and `users.acl`, each password has 64 hex characters, the 3 passwords differ, and each `user <name> on` line of the aclfile holds the password of its user

#### Scenario: A second plan changes nothing
- **WHEN** the keyring and the fake cluster hold the values of the first plan, and a test plans the push again
- **THEN** each of the 4 keys has the state `unchanged`, and `users.acl` has the same value

#### Scenario: The push before the merge
- **WHEN** a person runs `uv run devops k8s push-secrets --only devops/valkey-roadmap-auth` from the branch, and then the same command with `--plan`
- **THEN** each of the 4 keys reads `unchanged`, and no line holds a value

## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: devops-cli's cache Valkey requires its password and admits only namespace devops
The valkey container of `valkey-devops` SHALL read its users from the aclfile at `/run/valkey/users.acl`, mounted from key `users.acl` of Secret `valkey-devops-auth`. The redis-exporter container SHALL send `REDIS_USER=metrics` and key `metrics` of that Secret as `REDIS_PASSWORD`. The policy `valkey-devops-perimeter-ingress` SHALL admit namespace `devops` on TCP 6379 and namespace `monitoring` on TCP 9121, and the policy `valkey-devops-perimeter-egress` SHALL allow no egress.

#### Scenario: The devops cache Valkey's password and perimeter
- **WHEN** A person runs `kubectl -n llm get deployment valkey-devops -o yaml` and `kubectl -n llm get networkpolicy valkey-devops-perimeter-ingress valkey-devops-perimeter-egress -o yaml` on the cluster
- **THEN** The valkey container mounts key `users.acl` of `valkey-devops-auth` at `/run/valkey` and starts with `--aclfile /run/valkey/users.acl`, the exporter sets `REDIS_USER` to `metrics` and reads key `metrics`, the ingress policy admits exactly namespace `devops` on 6379 and namespace `monitoring` on 9121, and the egress policy has no egress rule

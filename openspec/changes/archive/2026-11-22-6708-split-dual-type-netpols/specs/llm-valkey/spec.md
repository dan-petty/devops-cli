## MODIFIED Requirements

### Requirement: devops-cli's cache Valkey requires its password and admits only namespace devops
The valkey container and the redis-exporter container of `valkey-devops` SHALL read the password from key `password` of Secret `valkey-devops-auth`, and the valkey container SHALL write it to a config file on a memory volume. The policy `valkey-devops-perimeter-ingress` SHALL admit namespace `devops` on TCP 6379 and namespace `monitoring` on TCP 9121, and the policy `valkey-devops-perimeter-egress` SHALL allow no egress.

#### Scenario: The devops cache Valkey's password and perimeter
- **WHEN** a person runs `kubectl -n llm get deployment valkey-devops -o yaml` and `kubectl -n llm get networkpolicy valkey-devops-perimeter-ingress valkey-devops-perimeter-egress -o yaml` on the cluster
- **THEN** both containers read `VALKEY_PASSWORD` or `REDIS_PASSWORD` from `valkey-devops-auth` key `password`, `valkey-devops-perimeter-ingress` admits exactly namespace `devops` on 6379 and namespace `monitoring` on 9121, and `valkey-devops-perimeter-egress` has no egress rule

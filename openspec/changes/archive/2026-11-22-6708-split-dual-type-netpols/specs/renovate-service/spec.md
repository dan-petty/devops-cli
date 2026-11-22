## MODIFIED Requirements

### Requirement: The Renovate pod reaches only DNS, the collector and public HTTPS
`devops-default-perimeter-ingress` and `devops-default-perimeter-egress` SHALL skip pods with `app.kubernetes.io/name: renovate`. NetworkPolicy `renovate-perimeter-ingress` SHALL select them and admit no ingress, and NetworkPolicy `renovate-perimeter-egress` SHALL select them and allow egress to CoreDNS, the collector on TCP 4318 and public TCP 443 with the except list of `devops-default-perimeter-egress`.

#### Scenario: A path to an internal service
- **WHEN** a throwaway pod with the label `app.kubernetes.io/name: renovate` in namespace `devops` runs `nc -w 3` to `github.com` on TCP 443, to the collector on TCP 4318, and to the gateway on TCP 4000, Valkey on TCP 6379, Qdrant on TCP 6333 and the API server on TCP 443, started with `kubectl run --rm -i --restart=Never`
- **THEN** the connects to `github.com` and to the collector succeed, and each connect to the gateway, Valkey, Qdrant and the API server times out

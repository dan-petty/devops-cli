## MODIFIED Requirements

### Requirement: No Ingress targets the logging namespace
No Ingress in the cluster SHALL route to a Service in namespace `logging`. `k8s/ingress/ingress-routes.yaml` SHALL NOT hold an Ingress named `loki-ingress`, and no Ingress document under `k8s/` SHALL set `metadata.namespace` to `logging`.

#### Scenario: The route list holds no loki-ingress
- **WHEN** a person runs `kubectl get ingress -A` on the cluster
- **THEN** no Ingress is named `loki-ingress`

#### Scenario: No Ingress document is in the logging namespace
- **WHEN** a person runs `kubectl -n logging get ingress` on the cluster
- **THEN** it lists no Ingress

### Requirement: The cert-manager perimeter admits only the metrics scrape and the API server
The NetworkPolicy `cert-manager-default-perimeter` SHALL admit ingress to every pod of namespace `cert-manager` only from namespace `monitoring` on TCP 9402, and SHALL allow egress only to CoreDNS and to the API server on TCP 443 and 6443 through an ipBlock that excludes 169.254.169.254/32. The NetworkPolicy `cert-manager-webhook` SHALL select only the webhook pods and admit only TCP 10250.

#### Scenario: The cert-manager perimeter peers
- **WHEN** a person runs `kubectl -n cert-manager get networkpolicy cert-manager-default-perimeter -o yaml` on the cluster
- **THEN** its one ingress rule admits namespace `monitoring` on TCP 9402, and its egress rules are CoreDNS on port 53 and the ipBlock on TCP 443 and 6443

#### Scenario: The webhook policy opens one port on the webhook pods
- **WHEN** a person runs `kubectl -n cert-manager get networkpolicy cert-manager-webhook -o yaml` on the cluster
- **THEN** it selects the pods with `app.kubernetes.io/name: webhook` and `app.kubernetes.io/component: webhook`, and its one ingress rule admits TCP 10250

### Requirement: Only the CloudNativePG operator reaches the Barman Cloud plugin
The NetworkPolicy `plugin-barman-cloud` in namespace `cnpg-system` SHALL select only the pods with `app.kubernetes.io/name: plugin-barman-cloud`, SHALL admit ingress only from the pods with `app.kubernetes.io/name: cloudnative-pg` on TCP 9090, and SHALL allow egress only to CoreDNS and to the API server on TCP 443 and 6443.

#### Scenario: The plugin policy peers
- **WHEN** a person runs `kubectl -n cnpg-system get networkpolicy plugin-barman-cloud -o yaml` on the cluster
- **THEN** its one ingress rule admits the operator pods on TCP 9090, and its egress rules are CoreDNS on port 53 and the API server ipBlock on TCP 443 and 6443

### Requirement: Egress to Qdrant on TCP 6333
The devops perimeter SHALL admit egress from the pods of namespace `devops` to namespace `llm` on TCP 6333 only.

#### Scenario: The policy admits the Qdrant port
- **WHEN** a person runs `kubectl -n devops get networkpolicy -o yaml` on the cluster
- **THEN** it finds one egress rule whose peer is the namespace selector of `llm` and whose only port is TCP 6333

## ADDED Requirements

### Requirement: The cert-manager perimeter admits only the metrics scrape and the API server
The NetworkPolicy `cert-manager-default-perimeter` SHALL admit ingress to every pod of namespace `cert-manager` only from namespace `monitoring` on TCP 9402, and SHALL allow egress only to CoreDNS and to the API server on TCP 443 and 6443 through an ipBlock that excludes 169.254.169.254/32. The NetworkPolicy `cert-manager-webhook` SHALL select only the webhook pods and admit only TCP 10250.

#### Scenario: The cert-manager perimeter peers
- **WHEN** a test reads `cert-manager-default-perimeter` in `k8s/cert-manager/networkpolicy.yaml`
- **THEN** its one ingress rule admits namespace `monitoring` on TCP 9402, and its egress rules are CoreDNS on port 53 and the ipBlock on TCP 443 and 6443

#### Scenario: The webhook policy opens one port on the webhook pods
- **WHEN** a test reads `cert-manager-webhook` in `k8s/cert-manager/networkpolicy-webhook.yaml`
- **THEN** it selects the pods with `app.kubernetes.io/name: webhook` and `app.kubernetes.io/component: webhook`, and its one ingress rule admits TCP 10250

### Requirement: Only the CloudNativePG operator reaches the Barman Cloud plugin
The NetworkPolicy `plugin-barman-cloud` in namespace `cnpg-system` SHALL select only the pods with `app.kubernetes.io/name: plugin-barman-cloud`, SHALL admit ingress only from the pods with `app.kubernetes.io/name: cloudnative-pg` on TCP 9090, and SHALL allow egress only to CoreDNS and to the API server on TCP 443 and 6443.

#### Scenario: The plugin policy peers
- **WHEN** a test reads `plugin-barman-cloud` in `k8s/cnpg-system/networkpolicy.yaml`
- **THEN** its one ingress rule admits the operator pods on TCP 9090, and its egress rules are CoreDNS on port 53 and the API server ipBlock on TCP 443 and 6443

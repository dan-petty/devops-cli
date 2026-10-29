## ADDED Requirements

### Requirement: No Ingress targets the logging namespace
No Ingress in the cluster SHALL route to a Service in namespace `logging`. `k8s/ingress/ingress-routes.yaml` SHALL NOT hold an Ingress named `loki-ingress`, and no Ingress document under `k8s/` SHALL set `metadata.namespace` to `logging`.

#### Scenario: The route list holds no loki-ingress
- **WHEN** a test reads the Ingress names in `k8s/ingress/ingress-routes.yaml`
- **THEN** no Ingress is named `loki-ingress`

#### Scenario: No Ingress document is in the logging namespace
- **WHEN** a test reads the Ingresses under `k8s/`
- **THEN** no Ingress sets `metadata.namespace` to `logging`

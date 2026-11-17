## MODIFIED Requirements

### Requirement: The Traefik Application installs a chart that ships Traefik v3.7.16
The Argo CD Application in `k8s/argocd/apps/traefik.yaml` SHALL install chart `traefik` from `https://traefik.github.io/charts` at version 42.1.1 or later, the first chart that ships Traefik v3.7.16. The values file `k8s/ingress/traefik-values.yaml` SHALL set no image tag, so the chart's own Traefik release runs.

#### Scenario: The Application pins a chart below the first one that ships v3.7.16
- **WHEN** a person runs `kubectl -n kube-system get deployment traefik -o jsonpath='{..image}'` on the cluster
- **THEN** the image is Traefik v3.7.16 or later, the release of the chart

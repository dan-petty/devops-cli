# traefik-release-pin Specification

## Purpose
The Traefik chart that the Argo CD Application `traefik` installs, and that `devops k8s deploy-stack` installs on a cluster without Argo CD. The chart ships a Traefik release with every published v3.7.x security fix.

## Requirements

### Requirement: The Traefik Application installs a chart that ships Traefik v3.7.16
The Argo CD Application in `k8s/argocd/apps/traefik.yaml` SHALL install chart `traefik` from `https://traefik.github.io/charts` at version 42.1.1 or later, the first chart that ships Traefik v3.7.16. The values file `k8s/ingress/traefik-values.yaml` SHALL set no image tag, so the chart's own Traefik release runs.

#### Scenario: The Application pins a chart below the first one that ships v3.7.16
- **WHEN** a test reads the chart source of the Application in `k8s/argocd/apps/traefik.yaml` and the values file `k8s/ingress/traefik-values.yaml`
- **THEN** the source's `repoURL` is `https://traefik.github.io/charts` and its `chart` is `traefik`
- **AND** its `targetRevision`, read as a version, is 42.1.1 or later
- **AND** the values set no `image.tag`

# Design

## Decisions

- **Enable the chart's argo-server with `authMode: client` and ServiceAccount `argo-workflows-ui`.**: Cloudflare Access is the front door, and the pasted token of a read-only account keeps the least privilege without a second identity provider.
- **Grant the read verbs in namespace `argo-workflows` only, and add the same Role in `devops` when the runner item lands.**: The controller watches only its own namespace today, so a `devops` grant would have no Workflow and no case to test.
- **Render the UI Ingress from `k8s/ingress/ingress-routes.yaml` under Application `ingress`.**: Stack `infra` maps to Application `ingress` in `CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS_BY_STACK`, so deploy-stack sets the configured domain on that host and on no host of the argo-workflows Applications.
- **Add namespace `argo-workflows` to the destinations of AppProject `homelab-system`.**: Application `ingress` runs in project `homelab-system`, whose destinations name no `argo-workflows`, and Argo CD refuses an object in a namespace that its project does not permit.
- **Keep the chart's own Ingress off and set the server's pod and container security context in the values.**: The namespace enforces Pod Security `restricted` and chart 2.0.18 leaves the server pod's context empty, and the chart's Ingress cannot take the deploy-time domain patch.
- **Put the Grafana links in ConfigMap `argo-workflows-ui-links` in `k8s/ingress/argo-workflows-ui-links.yaml`, and point the server at it with `--configmap`.**: Application `ingress` is patched at deploy time and its ConfigMap data values take the configured domain, as `open-webui-origins` already does, while Application `argo-workflows` has two sources and takes no patch.
- **Provision the community dashboard instead of a new one, and keep its case beside the ConfigMap size case of `tests/prometheus/test_k8s_monitoring_dashboards.py`.**: It reads the controller metrics that the chart already exposes, and a new dashboard costs more for the same panels.
- **Take the UI token with `kubectl create token argo-workflows-ui -n argo-workflows` and put no Secret in git.**: The repository holds no credential, and the token of a read-only account expires.
- **Split the links work into the manifest and gate case, then the test modules that list the ingress build objects and patches.**: A step changes at most 5 files, so the seven paths of the links work become a three-path group and a four-path group.
- **Defer the read-only grant in namespace `devops` and the start page link.**: No Workflow runs in `devops` yet, and the start page link waits for the start page items item.

## Rejected alternatives

- **SSO with an OIDC provider in front of the UI**: Cloudflare Access already authenticates the person at the host, and an OIDC provider adds a second identity path and a client Secret that no group of this plan covers.
- **`server` auth mode with the server ServiceAccount**: Every UI request would run as one broad account, so the read-only limit of the UI account would be unenforced; client mode passes the pasted token of `argo-workflows-ui` instead.
- **A read-only Role in namespace `devops` now**: `k8s/argo-workflows/values.yaml:25:singleNamespace: true` makes the controller watch only its own namespace, so no Workflow exists in `devops` and the grant would have no case.
- **Write access for resubmit in the UI account**: The owner allowed read only, and `kubectl auth can-i create workflows.argoproj.io` would answer `yes`, which fails the acceptance criterion.
- **Keep the UI Ingress in `k8s/argo-workflows/`**: `src/devops_cli/config/constants.py:1239:"infra": ("ingress",)` maps stack `infra` to Application `ingress` only, so deploy-stack writes no host patch for the argo-workflows Applications and the live host stays the placeholder.
- **Add a deploy-stack host patch for Application `argo-workflows` to fill the links in the chart's ConfigMap**: `k8s/argocd/apps/argo-workflows.yaml:10:sources:` gives that Application two sources, and `src/devops_cli/k8s/argocd_overrides.py:53:if spec.get("sources"):` guards a raise for such an Application, so deploy-stack cannot patch it.
- **Defer the Grafana Explore links to a later item**: The acceptance criterion of #4530 asks that the UI link open a Workflow's logs in Grafana, and the ConfigMap data patch of Application `ingress` carries the configured domain into the link, so no later item is needed.
- **Use the placeholder host in the Grafana links**: The link would open `grafana.example.com`, which no DNS record resolves, so the link would not open Grafana.
- **A new dashboard written from scratch**: The community dashboard covers the controller metrics, and `k8s/monitoring/dashboards/kustomization.yaml:58:- name: grafana-database-dashboards` shows the copy pattern the repository already uses for an upstream dashboard.
- **Keep the whole links change in one group of seven paths**: A task group changes at most 5 files, so a seven-path group would fail the check of the plan and overflow one implementation step.

## Security

The Argo Workflows UI becomes reachable from the internet through the Cloudflare tunnel and the Access application that covers `*.<domain>`, so the Argo server, its read-only account and the Grafana links cross the cluster trust boundary. A person must confirm that the Access application covers `workflows.<domain>`, that the pasted token of ServiceAccount `argo-workflows-ui` never enters git or a log, that `kubectl auth can-i` answers `no` for `create`, `update`, `patch` and `delete`, that the perimeter admits only Traefik on 2746 and the scrape on 9090, and that the links value holds the configured domain and no private host. `uv run devops ci --check --only k8s` fails if the perimeter admits another source or a manifest keeps the placeholder in a host or a link, and the `kubectl auth can-i` live check fails if a write verb answers `yes`.

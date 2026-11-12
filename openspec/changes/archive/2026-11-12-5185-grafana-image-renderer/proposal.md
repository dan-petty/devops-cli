# Proposal: #5185

## Why

Closes #5185. The Grafana of the cluster has no image renderer. On 2026-11-12 a render of panel 11 of dashboard `devops-cli-telemetry` (`/render/d-solo/...`, theme light) returned HTTP 500. So an agent cannot render a panel in the light and the dark theme to check a dashboard change, the Grafana MCP tool `get_panel_image` fails, and alerts and reports cannot hold a panel image.

## What Changes

- `k8s/monitoring/grafana-values.yaml` enables the image renderer of the `grafana` chart (`imageRenderer`): the image `grafana/grafana-image-renderer` at the release tag `v5.12.11` with `IfNotPresent`, requests of `100m` CPU and `512Mi` memory, limits of `2` CPUs and `1536Mi` memory, `GOMEMLIMIT=192MiB`, the ingress NetworkPolicy of the chart, and the token from Secret `grafana-image-renderer`. The values set no renderer URL and no callback URL, so the chart gives Grafana the Service DNS name of the renderer and gives the renderer the Grafana Service. No Ingress routes to the renderer.
- `src/devops_cli/k8s/cluster_secrets.py` gets the row `monitoring/grafana-image-renderer` (key `token`, keyring-only key `grafana_renderer_token`, generated with `token_urlsafe(32)`, stack `infra`), which restarts `deployment/grafana` and `deployment/grafana-image-renderer` when it changes. `devops k8s push-secrets` and `devops k8s deploy-stack` write it.
- The Argo CD project `homelab` ignores the pushed Secret as an orphan, as it does for the other pushed Secrets.
- `k8s/README.md` gets the section "Grafana Image Renderer" with the render check in the light and the dark theme, and the Secret in "Cluster Secrets".
- A manifest and the rows that `push-secrets` writes are observable, so the change carries a spec delta: the new capability `grafana-image-renderer`.

## Capabilities

- New: `grafana-image-renderer`.

## Impact

- One more Deployment in namespace `monitoring`. It reserves `100m` CPU and `512Mi` memory on a node with no GPU need, and no node selector or affinity names a node.
- The Grafana pod and the renderer pod do not start without Secret `monitoring/grafana-image-renderer`. `deploy-stack` pushes it before the Helm releases. On the cluster that Argo CD manages, a person pushes it before the sync of these values.
- The change fits one pull request.

## Feasibility

- Chart: `grafana-community/grafana` 14.4.1, the version that `k8s/argocd/apps/grafana.yaml` pins (`helm pull grafana --repo https://grafana-community.github.io/helm-charts --version 14.4.1`, appVersion 13.3.1). Its `values.yaml` has `imageRenderer.enabled: false`, `image.tag: latest`, `pullPolicy: Always`, `resources: {}` and `networkPolicy.limitIngress: true`. `values.schema.json` accepts `image.{registry,repository,tag,pullPolicy}` as strings, `env` as an open object, `resources` as an object and `existingSecret` as a string. `templates/_pod.tpl` sets `GF_RENDERING_SERVER_URL` to `http://<release>-image-renderer.<namespace>:8081/render` and `GF_RENDERING_CALLBACK_URL` to `http://<release>.<namespace>:80/` when `serverURL` and `renderingCallbackURL` are empty, and both pods read key `token` of `existingSecret`.
- The chart's own token Secret (`templates/image-renderer-secret.yaml`) takes its value from `lookup` and else `randAlphaNum 40`. The Helm documentation says that `lookup` returns an empty map in `helm template`, and Argo CD renders a chart with `helm template`. So the chart would make a new token at each new revision while the pods keep the old one. The value comes from the keyring instead, as for every other Secret of the stacks.
- Renderer release: `v5.12.11`, published 2026-11-11, is the newest release of `grafana/grafana-image-renderer` (`devops gh api repos/grafana/grafana-image-renderer/releases`). Docker Hub holds the tag with index digest `sha256:cfa6c8f63e6d626f90208f2880f15bd5facc279daec1b9bb642af07aa850d95e` for `linux/amd64` and `linux/arm64`. The documents of that tag (`docs/sources/_index.md`, `docs/sources/flags.md`) give `AUTH_TOKEN` as the token, port 8081 as the default, and `GOMEMLIMIT` below the memory limit, 1 GiB for each 8 GiB.
- Render: `helm template grafana <chart 14.4.1> --namespace monitoring --skip-tests -f k8s/monitoring/grafana-values.yaml` gives Deployment, Service (ClusterIP, port 8081) and NetworkPolicy `grafana-image-renderer-ingress` (port 8081 from the Grafana pods), no chart Secret and no Ingress. The Grafana container gets `GF_RENDERING_SERVER_URL=http://grafana-image-renderer.monitoring:8081/render`, `GF_RENDERING_CALLBACK_URL=http://grafana.monitoring:80/` and the token from `grafana-image-renderer`. `uv run devops k8s image-pins` resolves each of the 40 pinned images, the renderer included.
- Measurement: Grafana 13.3.1 and the renderer v5.12.11 in local containers, with the security context of the chart (user 1000, read-only root file system, no capabilities) and the limits above. 10 renders in a row of panel 11 of `devops-cli-telemetry`, light and dark, all returned `200 image/png` in 4 s to 7 s, and the renderer used 370 MiB at most. 3 renders at one time and one render of the 55 panels of the dashboard used 897 MiB at most (58 % of the limit), with no OOM kill. With no limit, 4 renders at one time used 1.1 GiB and 9 CPUs.
- The cluster runs Grafana 13.3.1 (`/api/health`). The namespace perimeter `monitoring-default-perimeter` admits all traffic between the pods of `monitoring`, so the renderer reaches the Grafana Service and Grafana reaches the renderer.

## Existing Tool Considered

The Grafana Image Renderer (Apache-2.0, Grafana Labs) is the renderer that the render API of Grafana supports, and the `grafana` chart deploys it through its `imageRenderer` values. A headless browser on a workstation works for one person, but not for the jobs in the cluster and the MCP tool. The change builds no code of its own beyond one row of the Secret table, and it deletes no internal code.

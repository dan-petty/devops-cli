# Design

## Decisions

- Use the `imageRenderer` values of the `grafana` chart. The chart makes the Deployment, the Service, the NetworkPolicy and the Grafana environment that points at the renderer, so the repository holds values only.
- Pin the image to the release tag `v5.12.11` with `IfNotPresent`. The other values files pin a tag, and the helm-values manager of Renovate reads `repository` and `tag`. `devops k8s image-pins` refuses `latest`, the default of the chart.
- Take the token from Secret `monitoring/grafana-image-renderer`, a row of the cluster Secret table with a generated value. Both pods read it at start, so a change restarts `deployment/grafana` and `deployment/grafana-image-renderer`.
- Resources from the measurement in the proposal: a request of `512Mi` holds one render (370 MiB at most), and a limit of `1536Mi` holds 3 renders at one time and a render of a dashboard of 55 panels (897 MiB at most). A CPU limit of `2` holds one render (about 1.9 CPUs at most). `GOMEMLIMIT=192MiB` is 1/8 of the memory limit, as the renderer documents ask.
- Keep the ingress NetworkPolicy of the chart (`limitIngress: true`). The namespace perimeter also admits the other pods of `monitoring`, so the token is the control that keeps other pods of the namespace out.
- Set no node selector and no affinity. The renderer has no volume, and a cordoned node gets no new pod.
- Keep the environment defaults of the chart. `HTTP_HOST` and `HTTP_PORT` are names of the renderer v4. The renderer v5 ignores them and listens on `:8081`, its default, which is the port of the chart.

## Rejected alternatives

- The token Secret of the chart: its template takes the value from `lookup`, else `randAlphaNum 40` (`templates/_helpers.tpl`, `grafana.imageRenderer.token`, chart 14.4.1). `lookup` returns an empty map in `helm template`, which Argo CD runs, so each new revision gives a new token and the pods keep the old one.
- The token Secret of the chart with an Argo CD `ignoreDifferences` on its data: the Secret would hold a value that no keyring holds, against the rule of "Cluster Secrets" that every Secret of the stacks comes from the keyring. When Argo CD makes the Secret again, the running pods keep the old token.
- `imageRenderer.token` in the values: it puts a secret in git.
- The default token `-` of the renderer and of Grafana: every pod of `monitoring` reaches port 8081 through the namespace perimeter, so a known token keeps nobody out.
- A ServiceMonitor for the metrics of the renderer: the acceptance check reads `container_memory_working_set_bytes` from cAdvisor, which Prometheus already has.

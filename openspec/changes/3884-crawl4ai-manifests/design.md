# Design

## Context

Crawl4AI renders hostile pages in Chromium that runs with `--no-sandbox`. Its in-app filter against internal addresses had critical bypasses in 0.8 and 0.9, and the project published more than ten advisories from 2026-06 to 2026-10. So the design trusts the NetworkPolicy first and the filter second.

## Decisions

- **The default perimeter skips the pod; the pod has its own policy.** `devops-default-perimeter` selects the pods of the namespace with `matchExpressions NotIn` on `app.kubernetes.io/name`, the shape that `portkey-perimeter` uses. A browser that renders hostile pages must not reach the gateway or the cache Valkey. *Rejected:* an extra deny policy. Policies only add allowances, so the pod would keep the allowances of the default perimeter.
- **Egress is DNS and public TCP 80 and 443.** The ranges removed are those of the default perimeter. Port 80 is new for this pod; the owner approved the egress on 2026-11-07, and plain HTTP pages would fail without it. *Rejected:* 443 only (plain HTTP pages fail).
- **Ingress is a pod selector peer alone.** The comment in the default perimeter records that kube-router refused a namespace and pod selector peer paired with `ports`.
- **The client rule is a separate file.** `roadmap-service-to-crawl4ai` sits in the `crawl4ai/` folder, so the manifests of the roadmap Service stay as they are, and a later service that the Service calls adds its own file.
- **User 999, numeric.** The image names `appuser`, which `runAsNonRoot` cannot check. The ID comes from the image layer (see Feasibility in the proposal).
- **An IPv4 bind.** `GUNICORN_BIND=0.0.0.0:11235`. The default `[::]:11235` takes IPv4 only when the node allows it.
- **Startup and readiness probes, no liveness probe.** `/health` is light, but gunicorn runs 4 threads, and a busy crawl could fail a liveness probe and kill a pod that works. supervisord restarts a dead process.
- **Limits are the first values.** Request 1 Gi, limit 4 Gi, CPU 2, as the compose file of the project sets; `/dev/shm` counts toward the limit. *Rejected:* a replacement of `config.yml` to lower the page pool. The copy would drift at each bump. Lower it only if a measurement on the cluster shows a need.
- **The image scan only reports.** The image is not ours to rebuild. A finding is fixed by the upstream release that Renovate brings. The job runs only when a pull request changes the Deployment.

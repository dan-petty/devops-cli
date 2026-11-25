# Design

## Decisions

- Expose `_application_renders` publicly as `application_renders` in `src/devops_cli/k8s/image_pins.py` so `k8s/catalog.py` uses the exact same `helm template` + `kubectl kustomize` Application render pipeline without duplicating source resolution or YAML normalization.
- Reuse `load_slo_specs` (`src/devops_cli/prometheus/slo_rules.py`) for `devops/monitoring/slos/*.yaml` and `load_specs` (`src/devops_cli/grafana/service_dashboard.py`) for `monitoring/dashboards/services.toml`.
- Resolve `gethomepage.dev/description` annotations for `Ingress` and `IngressRoute` resources by looking up each referenced backend `Service` (`(namespace, service_name)` across rendered Applications) and matching its `spec.selector` against workload metadata and pod-template labels; `Mattermost` carries both workload metadata and optional `spec.ingress.annotations`. Sort multiple UI descriptions per service by `(namespace, name)` and render separate lines (`<br>` in Markdown table rows, list in JSON).
- Implement `--dry-run` using local `discover_argocd_applications` and `application_sources` inspection without invoking `run_subprocess` or HTTP clients, printing planned Helm chart pulls (`chart`, `repoURL`, `targetRevision`) so `ProcessFake.calls` stays empty.
- Defer committed `k8s/CATALOG.md`, `k8s/catalog.toml` updates, `k8s/README.md` catalog links, `CONST_DOCS_INVENTORY`, and `.github/workflows/image-pins.yml` checks to `#7149` / `#5296` because the environment tree is frozen in `devops-cli`.

## Rejected alternatives

- Writing a second Helm/Kustomize renderer inside `k8s/catalog.py` duplicates `application_renders` and diverges from `image-pins`.
- Modifying `k8s/catalog.toml` or adding `k8s/CATALOG.md` in `devops-cli` fails `tests/gate/k8s_checks/environment_freeze.py` and `tests/docs/test_docs_inventory.py`.

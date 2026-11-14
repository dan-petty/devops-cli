# Design

## Decisions
- Set `grafana_folder: "dan-petty/devops-cli"` on `k8s/devops/dashboards/kustomization.yaml`.
- Set `grafana_folder: "Platform"` on `k8s/monitoring/dashboards/kustomization.yaml`.
- Add `$repo` variable to `roadmap-service-telemetry.json` with Prometheus query `label_values(devops_cli_service_jobs_total, repo)`.
- Enable "All" option for `$repo` variable with regex `.*` matching all repositories.
- Add `{repo=~"$repo"}` label filter to service metrics that record repository names.

## Rejected alternatives
- Generic folder names such as "DevOps Services": Rejected because they do not separate metrics across repositories.
- Repository short name "devops-cli": Rejected in favor of full repository name `dan-petty/devops-cli` for global uniqueness.

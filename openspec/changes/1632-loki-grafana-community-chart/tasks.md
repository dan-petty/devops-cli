# Tasks

## 1. Loki runs from the grafana-community chart

- [ ] 1.1 Write the failing test `test_loki_runs_the_grafana_community_chart_whose_loki_fixes_cve_2026_21729` in `tests/test_k8s_logging_stack.py`, and see it fail on the pins of `grafana/loki` 7.3.0 with `uv run devops ci test tests/test_k8s_logging_stack.py`
- [ ] 1.2 Set the `logging` stack in `src/devops_cli/commands/k8s/stack_lifecycle.py` to the `grafana-community` repository and `grafana-community/loki` 20.0.2, set the chart source of `k8s/argocd/apps/loki.yaml` to the same repository and version, name the new chart in the header of `k8s/logging/loki-values.yaml` and delete its `monitoring.selfMonitoring`; verify with `uv run devops ci test tests/test_k8s_logging_stack.py tests/test_k8s_argocd_apps.py tests/test_k8s.py tests/test_k8s_local_path_placement.py`
- [ ] 1.3 Render the chart with the values, and check the render against the live cluster without a change; verify with `helm template loki grafana-community/loki --version 20.0.2 -n logging -f k8s/logging/loki-values.yaml | kubectl apply --dry-run=server -n logging -f -`
- [ ] 1.4 Change the text that the new chart makes wrong: the note of #1133 in `k8s/logging/loki-values.yaml` names Loki 3.7.9 and its source lines, and `_loki_mode` in `tests/test_k8s_local_path_placement.py` names the chart default `Monolithic`. No command, option or message changes; verify with `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## Workflow follow-up

- #2439 deletes `loki-ingress`, whose backend the NetworkPolicy of `logging` blocks. This change keeps the policy closed (design.md).
- #2441 sets `deploymentMode: Monolithic` and turns off `memcached.enabled`. This change does not touch those keys, because a parallel change edits the same values file.
- Pending a person: after the merge, Argo CD syncs Application `loki`. Confirm that pod `logging/loki-0` runs `docker.io/grafana/loki:3.7.9`, is Ready and mounts claim `storage-loki-0`, and that the alerts `LokiRequestErrors` and `LokiRetentionNotRunning` do not fire.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

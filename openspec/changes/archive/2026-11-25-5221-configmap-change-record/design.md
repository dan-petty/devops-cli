# Design

## Decisions

- Use annotation prefix `roadmap.devops-cli/` (`roadmap.devops-cli/config-template-commit`, `roadmap.devops-cli/data-sha256`, `roadmap.devops-cli/changed-settings`, `roadmap.devops-cli/changed-at`, and optional `roadmap.devops-cli/change-reason`), preserving `app.kubernetes.io/` labels/annotations for application metadata and aligning with ADR 0022.
- Omit `roadmap.devops-cli/config-template-commit` when `git log -1 --format=%H -- configmap.example.yaml` returns empty outside a git checkout, while retaining `data-sha256`, `changed-settings`, and `changed-at`.
- Hash `data` via sorted canonical JSON SHA-256 (`configmap_data_sha256`) and diff `devops-cli.yaml` by flattened dotted leaf paths (`changed_configmap_settings`), treating lists such as `service.repos` as atomic leaf values so no config value ever enters annotations, history entries, or logs.
- Apply `devops-cli-config-sandbox` immediately after `devops-cli-config` inside `_apply_devops_configmap` (when provided) before creating/patching `devops-cli-config-changes` or logging `configmap_changed`, preserving existing sandbox ordering while ensuring no history or log entry is written unless `kubectl apply` succeeds.
- Store history in ConfigMap `devops-cli-config-changes` in namespace `devops` using `<epoch>-<sha256[:8]>` keys and single-line JSON values with UTC `%Y-%m-%dT%H:%M:%SZ` timestamps (`jq` `fromdateiso8601` compatible), updated via `kubectl patch --type merge` so concurrent deploys keep each key and prune entries older than 30 days.
- Emit `configmap_changed` at `logging.WARNING` on logger `devops_cli.k8s.configmap` with scalar `extra` attributes (`changed_settings` comma-joined string, `data_sha256`, `time`, plus optional `config_template_commit` and `change_reason`) so `OTelLoggingHandler` preserves every field.

## Rejected alternatives

- Splitting public settings into an Argo CD `configMapGenerator` (`Option A`) cannot track private `config.yaml` edits or changed setting names in one place.
- Relying on Loki alone fails when telemetry is disabled or unreachable; relying on a single `changes.jsonl` key loses updates under concurrent applies.
- Editing `k8s/argocd/apps/projects.yaml` in this repository is blocked by `tests/gate/k8s_checks/environment_freeze.py` and tracked in `#7148`; enabling kube-apiserver audit logging is tracked in `#6428`.

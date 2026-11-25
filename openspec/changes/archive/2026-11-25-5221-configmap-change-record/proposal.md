# Proposal: #5221

## Why

The live ConfigMap `devops-cli-config` changed 21 times in the 7 days to 2026-11-12 without any record of which settings changed, which template commit was rendered, when each apply happened, or why it ran. The ConfigMap holds model selections, Service modes, budgets, and timeouts that directly affect project review findings (#5219) and job outcomes.

## What Changes

- Add pure ConfigMap change-record helpers in `src/devops_cli/k8s/configmap.py` to hash rendered `data`, diff dotted setting paths without values, read the template's last git commit, annotate changed `devops-cli-config` manifests, construct and prune 30-day entries in `devops-cli-config-changes`, and emit a `configmap_changed` WARNING log record.
- Add `_apply_devops_configmap` and `--reason` support in `src/devops_cli/commands/k8s/stack_lifecycle.py` so both `_deploy_native_manifests` and `_handle_argo_managed_deployment` compare live data before applying, apply the credential-free sandbox copy next, and create/patch `devops-cli-config-changes` plus log only after `kubectl apply` exits zero on changed data.
- Add shared ConfigMap annotation, history object, retention, and logging constants in `src/devops_cli/config/constants.py` and option help in `src/devops_cli/lang/en/help.py`.
- Document the annotations, history object, `configmap_changed` WARNING log record, and 7-day `jq` query in `k8s/README.md`, keeping `docs/CLUSTER.md` Go-live check commands unchanged, and regenerate CLI documentation (`docs/CLI_REFERENCE.md`, `docs/commands/k8s.md`).

## Capabilities

### New Capabilities

- `devops-configmap-change-record`: Record each live `devops-cli-config` change with `roadmap.devops-cli/` annotations, merge-patched entries in ConfigMap `devops-cli-config-changes` queryable over 7 days, and a `configmap_changed` WARNING telemetry log without storing setting values.

## Impact

- Runtime code: `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/k8s/configmap.py`, `src/devops_cli/commands/k8s/stack_lifecycle.py`.
- Tests and docs: `tests/k8s/test_k8s_configmap.py`, `tests/commands/k8s/test_k8s.py`, `k8s/README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/k8s.md`.

## Feasibility

- Today `devops k8s deploy-stack --stack devops` calls `_render_devops_configmaps` and `render_active_devops_configmap` (`src/devops_cli/k8s/configmap.py`) to merge `k8s/devops/configmap.example.yaml` with local `config.yaml` (`service.repos`, `service.github_app`, `ai`, `telemetry`) and sends the rendered manifest to `kubectl apply -f -` via `_apply_rendered` (`src/devops_cli/commands/k8s/stack_lifecycle.py`) on both `_deploy_native_manifests` and `_handle_argo_managed_deployment`, followed immediately by `devops-cli-config-sandbox`. Argo CD ignores `devops-cli-config` in `k8s/argocd/apps/projects.yaml` (`orphanedResources.ignore`), and `docs/CLUSTER.md` keeps the operator Go-live check commands.
- Chosen path is Option B (extended): `_apply_devops_configmap` reads live `devops-cli-config` data, computes changed dotted setting names without values, writes `roadmap.devops-cli/` annotations (the prefix declared in `docs/adr/0022-one-repository-reference-names-the-objects-labels-and-keys-of-each-repository.md`), applies the manifest (and sandbox copy), creates ConfigMap `devops-cli-config-changes` when absent, sends one merge patch adding `<epoch>-<sha256[:8]>` and pruning entries older than 30 days, and logs `configmap_changed` at `WARNING` on `devops_cli.k8s.configmap` so `OTelLoggingHandler` (`src/devops_cli/telemetry/logging_bridge.py`) exports it without modifying the allowlist.
- Deferred work: Option A (moving public settings to Argo CD `configMapGenerator`) leaves private `config.yaml` values and field diffs unrecorded; direct `kubectl edit` and `kubectl patch` capture via Kubernetes audit logging is deferred to `#6428`; adding `devops-cli-config-changes` to `orphanedResources.ignore` in `k8s/argocd/apps/projects.yaml` is deferred to `#7148` in `dan-petty/homelab` because `tests/gate/k8s_checks/environment_freeze.py` freezes `k8s/argocd/apps/projects.yaml` in `devops-cli`.

## Existing Tool Considered

Argo CD (`https://github.com/argoproj/argo-cd`, Apache-2.0, maintained) is already in use and covers only Git-tracked public templates. Splitting the ConfigMap via Option A would cost about 0.6 M tokens and 3 hours while still missing `config.yaml` values, dotted setting diffs, and 7-day queries. Extending `deploy-stack` with Option B builds only pure comparison, annotation, merge-patch, and log helpers (~0.4 M tokens and 2 hours to build; runtime cost of one live ConfigMap read, one history read, one initial empty ConfigMap apply when absent, one merge patch, and one WARNING log record per changed apply).

# Proposal: #5535

## Why

The service catalog, workload/store inventory, SLO links, and cluster class tables were maintained by hand and drifted out of sync with the manifests rendered by Argo CD Applications.

## What Changes

- Rename `_application_renders` in `src/devops_cli/k8s/image_pins.py` to public `application_renders` so `devops k8s catalog` shares the existing Helm and Kustomize Application renderer without duplicating render logic.
- Add `src/devops_cli/k8s/catalog.py` and `CatalogError` in `src/devops_cli/exceptions/k8s.py` to extract workloads (including CloudNativePG `Cluster` and `Mattermost`), stores (`PersistentVolumeClaim`, `volumeClaimTemplates`, `Cluster`, `ScheduledBackup`), cluster classes (`PriorityClass`, `RuntimeClass`, `StorageClass`), UI descriptions (`gethomepage.dev/description` resolved via backend `Service` selectors across `Ingress`, `IngressRoute`, and `Mattermost.spec.ingress.annotations`), `catalog.toml` entries with `fnmatch` globs, Sloth specs from `devops/monitoring/slos/`, and service dashboards from `monitoring/dashboards/services.toml`.
- Add `devops k8s catalog [--k8s-dir DIR] [--check] [--format markdown|json] [--dry-run]` in `src/devops_cli/commands/k8s/catalog.py`, registered under `src/devops_cli/commands/k8s/__init__.py` with option help in `src/devops_cli/lang/en/help.py` and generated CLI reference updates.
- Add hermetic offline fixture tests in `tests/k8s/test_k8s_catalog.py`.

## Capabilities

### New Capabilities

- `k8s-service-catalog`: Generate, check, dry-run, and serialize (`markdown` or `json`) the Kubernetes service catalog from rendered Argo CD Applications, `catalog.toml`, Sloth SLO specs, service dashboards, and Homepage UI annotations.

## Impact

- Runtime code: `src/devops_cli/k8s/image_pins.py`, `src/devops_cli/k8s/catalog.py`, `src/devops_cli/commands/k8s/catalog.py`, `src/devops_cli/commands/k8s/__init__.py`, `src/devops_cli/exceptions/k8s.py`, `src/devops_cli/lang/en/help.py`.
- Tests and generated docs: `tests/k8s/test_k8s_catalog.py`, `docs/CLI_REFERENCE.md`, `docs/commands/k8s.md`, `docs/MCP_TOOLS.md`, `tests/ai/mcp/__snapshots__/test_mcp_tool_listing/test_the_tool_listing_matches_the_snapshot.json`.

## Feasibility

- Checked `src/devops_cli/k8s/image_pins.py:245` (`_application_renders`), `src/devops_cli/k8s/environment.py` (`resolve_environment`, `EnvironmentTree`), `src/devops_cli/prometheus/slo_rules.py` (`load_slo_specs` reading `k8s/devops/monitoring/slos/`), and `src/devops_cli/grafana/service_dashboard.py` (`load_specs` reading `k8s/monitoring/dashboards/services.toml`): all three readers and the shared renderer already exist and are reused directly.
- Checked `tests/gate/k8s_checks/environment_freeze.py` (`tests/invariants/test_environment_freeze_check.py:27`: `is_environment_path("k8s/catalog.toml") == True`) and `tests/docs/test_docs_inventory.py`: committed `k8s/CATALOG.md`, `k8s/catalog.toml` edits, `k8s/README.md` environment link, `CONST_DOCS_INVENTORY` generated entry, and workflow CI check stay deferred to `#7149` / `dan-petty/homelab` (`#5296`), while `#5535` delivers the `devops k8s catalog` command, its offline fixture tests, and regenerated CLI docs.

## Existing Tool Considered

Backstage (`https://github.com/backstage/backstage`, Apache-2.0, maintained) covers general service metadata portals from per-component `catalog-info.yaml` files, but cannot render Helm/Kustomize Argo CD Applications, read `k8s/catalog.toml`, resolve Traefik/`Ingress` selectors for `gethomepage.dev/description`, join Sloth SLOs and `services.toml` dashboards, or run `--check` on generated Markdown (~280 lines plus tests, ~320k tokens / ~1 agent-day).

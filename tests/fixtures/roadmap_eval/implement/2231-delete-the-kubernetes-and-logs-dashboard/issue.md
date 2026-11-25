## Friction

The Kubernetes tab of `devops dashboard` and its Logs tab do a part of what k9s does, and k9s is already pinned and installed. VISION item 15 says that `devops dashboard` covers only what no open tool covers. #1885 audits each dashboard tab against open tools. This item is the result of that audit for the Kubernetes and Logs tabs. Four open items (#807, #808, #809, #811) would add more code to the same tab.

## Evidence

What the tabs do, and what k9s v0.51.0 does in their place:

| Dashboard | k9s |
| :--- | :--- |
| Pod list for all namespaces, with status, restarts and age | `k9s -A -c pods` |
| Namespace selector | `:ns` |
| `/` filter by namespace, name or status | `/` (regex), `/-l <selector>` (labels) |
| `e`: the events of a pod (`ui/pod_inspector.py`) | `d` (describe; the events are at the end) |
| Logs tab: live log of a pod, container switch | `l` on a pod; `Enter` opens its containers |
| Count of Ready nodes in the banner | `:nodes`, with CPU and memory use and the GPU columns |
| `r`: refresh | Not needed: k9s watches each resource that it shows |

- k9s v0.51.0 is in `src/devops_cli/tools_lock/tools.lock` with a SHA-256 for each platform. `devops install-tools` and the devcontainer post-create install it (`docs/DEVCONTAINER_USAGE.md`). `k9s --help` of v0.51.0 has `-A`, `-c`, `--context` and `--readonly`.
- The installed k9s v0.51.0 binary holds the node view columns `GPU/A` and `GPU/C` for `nvidia.com/gpu` and `amd.com/gpu` (`strings` of the binary, 2026-10-25).
- The Logs tab streams only pod logs. Its one source is `pod_log_source` (`ui/dashboard.py:308`), and its title is "Select a pod on the Kubernetes tab" (`ui/dashboard.py:213`).
- These stay, because other commands use them: `KubernetesService.read_pod_logs` (`commands/argo.py`, `commands/k8s/cluster_context.py`), `PodInfo` (`k8s/informer.py`, `output/formatters/tables.py`) and `k8s/service_http.py` (the Telemetry and Valkey tabs).

What the tabs do that k9s does not:

- `devops dashboard --summary` prints the pods, unhealthy pods first, without a full-screen interface. `kubectl get pods -A` gives the same data.
- One window holds the Kubernetes, Docker, Telemetry and Valkey tabs. k9s shows only Kubernetes. The other tabs stay until #1885 decides them.

Request cost:

- Now: while the dashboard runs, each refresh (default 5 seconds, `--refresh-interval`) sends one LIST of every pod in all namespaces and one LIST of every node (`fetch_k8s_status` and `_node_readiness` in `ui/data_providers.py`).
- k9s: it lists each resource that it shows one time and then watches it. For the CPU and memory columns, it reads `metrics.k8s.io` at its refresh rate (`refreshRate`, default 2 seconds). It sends nothing when it does not run.
- No GitHub requests in either case.

## Proposed remedy

Delete the two tabs and everything that only they use. The lists come from function and class names on `origin/main` 1bb164bd. Check the users of each name with grep when you write the change.

Source:

- `ui/log_buffer.py` (186 lines) and `ui/pod_inspector.py` (114 lines), the whole files.
- `ui/widgets.py`: `K8sPanel` and `LogPane` (about 410 lines), their `__all__` entries and their imports.
- `ui/projections.py`: `_k8s_nodes`, `k8s_banner`, `k8s_filter_banner`, `k8s_pod_row`, `k8s_rows`, `k8s_identities`, `pod_matches`, `filter_pods`, `namespace_choices`, `pod_container_names`, `pod_container_rows` and `pod_event_rows` (about 80 lines), and their registry entries.
- `ui/data_providers.py`: `K8sSummary`, `_get_k8s_client`, `_in_a_pod`, `_kubeconfig_context`, `_k8s_context_name`, `_node_readiness`, `fetch_k8s_status` and `fetch_pod_events` (about 90 lines).
- `ui/refresh.py`: `PodLogSource`, `pod_log_source` and the Kubernetes provider entry (about 50 lines).
- `ui/dashboard.py`: `_tail`, `action_next_container`, the Logs `TabPane`, the `l` binding, the `K8sPanel` entry of `_PANELS`, the pod handler of `on_data_table_row_selected` and the pod lines of the help screen.
- `commands/dashboard.py`: `_render_k8s_panel` and its call from `--summary`.
- `config/constants.py:3093-3142`: `CONST_DASHBOARD_DOMAIN_K8S`, its entries in the domain list, the labels and the tab focus, and `CONST_LOGS_TAB_ID`.
- `config/defaults.py:765-767`: `DEFAULT_K8S_POD_EVENT_LIMIT` and `DEFAULT_DASHBOARD_SUMMARY_POD_ROWS`.
- `lang/en/help.py:1606` and the `--tab` default: the first tab becomes Docker, and the help becomes `(1=docker, 2=telemetry, 3=valkey)`.
- `tests/fixtures/swallowed_failures_ceilings.json`: lower the ceiling of each changed module to what stays.

Tests: delete the pod, log and inspector tests in `tests/test_ui_reactive.py` (63 functions by name, about 980 lines) and `tests/test_ui_dashboard.py` (7 functions, about 120 lines). Keep the `PodInfo` tests in `tests/test_k8s_models.py`.

Docs: `devops docs generate --sync-readme` refreshes `docs/commands/dashboard.md`, `docs/commands/tui.md` and `docs/CLI_REFERENCE.md`. In `docs/DEVCONTAINER_USAGE.md`, say that k9s replaces the Kubernetes and Logs tabs.

## What it deletes

About 890 source lines and about 1,100 test lines (counted by function and class names; count the exact set in the change), and the 5-second poll of the cluster.

## Pin and config to ship

None. k9s v0.51.0 is already in `tools.lock`. k9s reads the kubeconfig contexts that `devops k8s` uses. Its defaults show what the tabs show, so no k9s config is shipped.

## Person-run steps

None to install. To look at the cluster with no risk of a change, start k9s with `--readonly`.

## Existing Tool Considered

k9s (https://k9scli.io, Apache-2.0, maintained; v0.51.0 released 2026-06-06).

## Cost (written)

The change deletes code, so it has no upkeep. It needs about half a day and about 30k to 50k tokens (estimate), most of it for the many small edits.

## Related

- #1885: the audit. This item is its Kubernetes and Logs section.
- #1904: `--tab` with an unknown tab. The tab list changes here.
- #1334: the split of the dashboard test suite. This item removes a part of it.
- #807 and #809 are closed as not planned, because k9s covers them. #808 (masked pod manifest) and #811 (port-forwards and service URLs in the dashboard) lose their tab. A person decides them.

## Acceptance criteria

- `devops dashboard` starts on the Docker tab and has no Kubernetes tab and no Logs tab.
- `devops dashboard --summary` prints no Kubernetes panel and sends no request to a cluster.
- No module under `src/devops_cli/ui/` imports the `kubernetes` package, `devops_cli.k8s.service` or `devops_cli.k8s.context`.
- The dashboard tests pass with three domains, and `devops docs check` passes.


Source: https://github.com/dan-petty/devops-cli/issues/1885

regression of #1883

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=bb46660c8d12e28520a25e8171ec300c627df0db -->
## Proposed design

### Problem statement
The `devops dashboard` Kubernetes tab and Logs tab duplicate functionality that k9s v0.51.0 already provides. k9s is pinned in `tools.lock` and installed by `devops install-tools`. This item deletes both tabs and all code that only they use. It removes about 890 source lines, about 1,100 test lines, and the 5-second cluster poll.

### Acceptance criteria
- Criterion 1: `devops dashboard` starts on the Docker tab and shows no Kubernetes tab and no Logs tab.
  Verification: Run `devops dashboard` in a terminal. Confirm the first tab is Docker and the tab bar shows only Docker, Telemetry, and Valkey.
- Criterion 2: `devops dashboard --summary` prints no Kubernetes panel and sends no request to a cluster.
  Verification: Run `devops dashboard --summary` with no cluster running. Confirm no Kubernetes section appears in the output and no connection error is shown.
- Criterion 3: No module under `src/devops_cli/ui/` imports the `kubernetes` package, `devops_cli.k8s.service`, or `devops_cli.k8s.context`.
  Verification: Run `grep -r 'import kubernetes\|from kubernetes\|devops_cli.k8s.service\|devops_cli.k8s.context' src/devops_cli/ui/`. Confirm no matches.
- Criterion 4: The dashboard tests pass with three domains and `devops docs check` passes.
  Verification: Run `uv run pytest tests/test_ui_reactive.py tests/test_ui_dashboard.py` and `uv run devops docs check`. Confirm both pass.

### Key questions
- **What is the status of #808 and #811 after this item is delivered?**: They lose their tab. A person decides whether to close them or redirect them to another surface. This decision does not block delivery of this item. (proposed)
- **What entries in `swallowed_failures_ceilings.json` change?**: `src/devops_cli/ui/pod_inspector.py` (ceiling 1) is removed because the file is deleted. The ceilings of `src/devops_cli/ui/dashboard.py` (1), `src/devops_cli/ui/data_providers.py` (11), `src/devops_cli/ui/refresh.py` (1), and `src/devops_cli/ui/widgets.py` (2) are lowered to match the remaining code. [sources: tests/fixtures/swallowed_failures_ceilings.json]
- **Does this item depend on #1904 or #1334?**: No. #1904 handles an unknown `--tab` value and works regardless of which tabs exist. #1334 splits the dashboard test suite; this item removes a part of it. Neither must be done first. (proposed)

### Open questions
- What code stays because other commands or tabs use it? (missing verified source)
- What is the new default tab and the new tab order after deletion? (missing verified source)
- What happens to the `--summary` Kubernetes panel? (missing verified source)

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

<!-- devops-roadmap-alternatives:start -->
Alternatives check of 2026-11-03: not-applicable.
Class: refactor, no search.
Tool: none found.
<!-- devops-roadmap-alternatives:end -->

<!-- devops-roadmap-record {"Effort": "High", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium", "alternatives.body_hash": "c85f78a78d83797c40b0424fc147f6ced42d03744e73724e672af7a7d3896156", "alternatives.checked_at": "2026-11-03T02:02:22.150175+00:00", "alternatives.failed_at": null, "alternatives.failed_error": null, "alternatives.tool": null, "alternatives.verdict": "not-applicable", "refine.block_paths": null, "refine.blocked_by": null, "refine.body_hash": "c85f78a78d83797c40b0424fc147f6ced42d03744e73724e672af7a7d3896156", "refine.commented_at": "2026-10-28T07:49:55+00:00", "refine.comments_seen": "4", "refine.failed_body_hash": null, "refine.needs_split": "false", "refine.next_step": "person", "refine.section_hash": "ee8f318f75f2018d1ed83197b73d4133f0abb3ba917212c6491384ee11706cd1", "refine.wait_refs": null} -->

# Proposal

## Why

The `duckduckgo` engine of SearXNG answers a CAPTCHA with `suspended_time=0`, so SearXNG suspends nothing and the next query asks it again, while other engines answer `Too many request`. A refused engine leaves no trace in `devops_cli_web_searches_total`, because a reply that another engine filled counts `ok`. #4201 needs a measure of each engine before anyone can name the cause or choose the engine set, so this change enables the SearXNG OpenMetrics endpoint and scrapes its per-engine series.

## What Changes

- `k8s/devops/searxng/configmap.yaml` sets `general.open_metrics` to the placeholder `${SEARXNG_METRICS_PASSWORD}`, and the settings hold no password and no retry key.
- `k8s/devops/searxng/deployment.yaml` adds the `render-settings` init container that writes `/etc/searxng/settings.yml` into the `settings-rendered` `emptyDir` from the settings ConfigMap and key `password` of Secret `searxng-metrics-auth`, and the `searxng` container mounts that rendered file.
- `src/devops_cli/k8s/cluster_secrets.py` adds row `devops/searxng-metrics-auth` of type `kubernetes.io/basic-auth` with literal user `searxng`, keyring password `searxng_metrics_password` and a restart of `deployment/searxng`, and `k8s/README.md` lists its rows.
- `k8s/devops/searxng/servicemonitor.yaml` scrapes `/metrics` of Service `searxng` on port `http` every 15 s with basic auth from Secret `searxng-metrics-auth`; `k8s/devops/searxng/kustomization.yaml` lists it and `PRODUCT_POST_HELM_BY_STACK` of the `devops` stack applies it after the Helm releases.
- `k8s/devops/searxng/networkpolicy.yaml` admits namespace `monitoring` to TCP 8080 in an ingress rule of its own, and `_admits` of `tests/gate/k8s_checks/network_policies.py` counts a peer only when its namespace selector names no namespace or namespace `devops`.
- `k8s/monitoring/networkpolicy.yaml` admits namespace `devops` to TCP port 8080 beside port 8000, so the scrape leaves the monitoring namespace.
- `docs/CLUSTER.md` records the placeholder, the render, the scrape and the two perimeters.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `searxng-service`: The settings hold an OpenMetrics password placeholder, The pod renders its settings at start, A ServiceMonitor scrapes the engine metrics, Only the roadmap Service calls the pod, The pod meets Pod Security restricted, The deploy stack and the kustomizations list every file
- `k8s-network-policies`: The monitoring perimeter admits the SearXNG metrics scrape
- `stack-credential-sync`: The SearXNG metrics Secret row comes from the keyring

## Impact

- Code: `src/devops_cli/k8s/cluster_secrets.py`, `k8s/devops/searxng/configmap.yaml`, `k8s/devops/searxng/deployment.yaml`, `k8s/devops/searxng/servicemonitor.yaml`, `k8s/devops/searxng/kustomization.yaml`, `src/devops_cli/commands/k8s/stack_lifecycle.py`, `k8s/devops/searxng/networkpolicy.yaml`, `k8s/monitoring/networkpolicy.yaml`
- Documents: `k8s/README.md`, `docs/CLUSTER.md`
- Tests: `tests/invariants/test_k8s_searxng.py`, `tests/invariants/test_k8s_manifests.py`, `tests/k8s/test_cluster_secret_push.py`, `tests/k8s/test_cluster_secret_plan.py`, `tests/commands/k8s/test_k8s.py`, `tests/k8s/test_image_pins.py`, `tests/commands/k8s/test_k8s_devops_stack.py`, `tests/gate/k8s_checks/network_policies.py`, `tests/commands/test_review_rules_pack.py`, `tests/k8s/test_k8s_argo_workflows.py`, `tests/security/test_review_score.py`, `tests/server/routes/test_k8s_roadmap_service.py`

## Feasibility

- The probes confirm the two manifests that the change edits, word for word: The path `k8s/devops/searxng/configmap.yaml` is a file of the staging commit. The path `k8s/devops/searxng/networkpolicy.yaml` is a file of the staging commit.
- The probes show that the monitor is no file yet, word for word: The path `k8s/devops/searxng/servicemonitor.yaml` is no file at the root of the staging commit. These files of the commit are candidates: `k8s/llm/gateway/servicemonitor.yaml`. No commit in the history deleted or renamed it. Group 5 creates the monitor and lists it in `creates`.
- The probes show that the settings key is no path of the repository, word for word: The path `general.open_metrics` is no file of the staging commit. No commit in the history deleted or renamed it. The key is a setting of the pinned image, and group 3 adds it.
- `search_code` of `PRODUCT_POST_HELM_BY_STACK` returned the statement `PRODUCT_POST_HELM_BY_STACK: dict[str, tuple[Path, ...]] = {` in `src/devops_cli/commands/k8s/stack_lifecycle.py`, so a ServiceMonitor of the product base belongs to the post-Helm table and not to the pre-Helm one.
- `read_file` of `k8s/llm/kustomization.yaml` showed `k8s/llm/kustomization.yaml:12:- gateway/servicemonitor.yaml`, the pattern that group 5 follows for the SearXNG monitor.
- `read_file` of `tests/gate/k8s_checks/deploy_stack.py` showed `tests/gate/k8s_checks/deploy_stack.py:76:def check_prometheus_operator_crds_install_before_every_service_monitor() -> None:` and `tests/gate/k8s_checks/deploy_stack.py:139:[("llm", "llm/gateway/servicemonitor.yaml")],`, so a ServiceMonitor of the product base belongs to the post-Helm table and not to the pre-Helm one.
- `read_file` of `tests/support/k8s_tree.py` showed `tests/support/k8s_tree.py:32:def deploy_stack_manifests(stacks: Iterable[str] | None = None) -> list[Path]:`, whose body builds the pre-Helm list from `PRODUCT_MANIFESTS_BY_STACK` only, so group 5 adds the monitor to `PRODUCT_POST_HELM_BY_STACK`.
- `read_file` of `tests/commands/k8s/test_k8s_devops_stack.py` showed `tests/commands/k8s/test_k8s_devops_stack.py:38:paths = PRODUCT_MANIFESTS_BY_STACK["devops"]`, the module where group 5 writes its failing test.
- `search_code` of `PRODUCT_POST_HELM_BY_STACK` showed `tests/invariants/test_architectural_invariants.py:970:(PRODUCT_POST_HELM_BY_STACK, product),`, so the path that group 5 adds to the table needs its file in the same step, and group 5 creates the monitor.
- `search_code` of `PRODUCT_POST_HELM_BY_STACK` showed `k8s/README.md:25:Register each manifest and post-Helm step that runs in the cluster in`, the rule that group 5 follows for the monitor.
- `read_file` of `k8s/llm/gateway/servicemonitor.yaml` showed `k8s/llm/gateway/servicemonitor.yaml:14:- port: http`, the monitor that group 5 follows: it carries no Prometheus release label, so a monitor in namespace `devops` is selected like the one in namespace `llm`.
- `read_file` of `k8s/devops/searxng/service.yaml` showed `k8s/devops/searxng/service.yaml:15:port: 8080` on port name `http`, and `read_file` of `k8s/devops/searxng/deployment.yaml` showed `k8s/devops/searxng/deployment.yaml:75:mountPath: /etc/searxng/settings.yml` and `k8s/devops/searxng/deployment.yaml:119:name: searxng-settings`, so the render replaces the one mounted file of the ConfigMap volume.
- `read_file` of `k8s/devops/searxng/deployment.yaml` showed `k8s/devops/searxng/deployment.yaml:124:sizeLimit: 128Mi` and the pod security context of user 977 with group 977, so the new `emptyDir` and the init container follow the controls that the pod already sets.
- `read_file` of `tests/gate/k8s_checks/network_policies.py` showed `tests/gate/k8s_checks/network_policies.py:160:any(_selects(peer.get("podSelector", {}), labels) for peer in rule.get(side, []))` and `tests/gate/k8s_checks/network_policies.py:208:) == (True, True, False)`, so a peer with no pod selector counts as admitting every pod of namespace `devops`; group 6 changes `tests/gate/k8s_checks/network_policies.py:def _admits` to skip a peer whose namespace selector names another namespace, and `tests/gate/k8s_checks/network_policies.py:def check_the_service_and_the_stage_job_reach_searxng_and_the_runner_job_does_not` keeps asserting that the runner Job pod reaches no SearXNG port.
- `read_file` of `k8s/monitoring/networkpolicy.yaml` showed `k8s/monitoring/networkpolicy.yaml:151:port: 8000` in the `devops` peer and no port 8080 in that peer, so group 7 adds the scrape port to that peer and to no other.
- `read_file` of `k8s/devops/searxng/kustomization.yaml` showed `k8s/devops/searxng/kustomization.yaml:4:- configmap.yaml`, the resource list that group 5 extends with the monitor.
- `read_file` of `src/devops_cli/k8s/cluster_secrets.py` showed `_BASIC_AUTH_SECRET_TYPE: SecretType = "kubernetes.io/basic-auth"` at line 45 and `SEARXNG_SERVER_KEY = "searxng_secret_key"` at line 47, so the table already declares the basic-auth type and the keyring-only key shape that group 1 reuses.
- `read_file` of `tests/invariants/test_k8s_searxng.py` showed `tests/invariants/test_k8s_searxng.py:16:(row,) = [secret for secret in CLUSTER_SECRETS if secret.ref == "devops/searxng"]`, the shape that the new case of group 1 follows; `tests/invariants/test_k8s_manifests.py:126:def test_readme_lists_the_table() -> None:` compares the table with the README, whose Cluster Secrets header is `k8s/README.md:756:| Secret | Key | Source | Required | When the keyring has no value | Stack | Restarted when it changes |` and whose SearXNG row holds `k8s/README.md:769:devops/searxng`, so group 1 writes the table row and its README rows in one step.
- Not checked: the `general.open_metrics` key and the series that the endpoint serves, because this run read no SearXNG source or documentation; the first scrape of the new monitor confirms them, and no requirement names a series.
- Not checked: the CAPTCHA with `suspended_time=0`, the `Too many request` lines and the 3-hour log of 2026-11-08, because this run read no log; #6753 reads the series after at least 3 days of traffic.
- Not checked: that the pinned image ships `sh` and `sed` for the render; the first `devops k8s searxng-check` after the rollout confirms the rendered file, and a person reads it once before the merge.
- `devops k8s searxng-check` needs a client of the cluster and a network as preconditions of the call, and a person runs it after the rollout of the new Deployment.
- `devops k8s push-secrets --only devops/searxng-metrics-auth` needs the workstation keyring and a client of the cluster as preconditions, and a person runs the real push before the Deployment of group 4 rolls out, because the init container reads that Secret.
- `devops k8s deploy-stack --stack devops --dry-run` needs a checkout of this repository and runs `kubectl kustomize` on local files, with no cluster.
- The first checks that the implementation runs against the real system are `uv run devops ci test tests/invariants/test_k8s_searxng.py`, `uv run devops ci test tests/commands/k8s/test_k8s_devops_stack.py`, `uv run devops ci --check --only k8s` and `uv run devops ci docs`.
- No verify program is new: `pytest`, `kubectl`, `kube-linter`, `ruff` and `mypy` are in the runner image, so the failure classes that a step can hit are `test`, `lint` and `types`, which a repair fixes, and the pod runs with readOnlyRootFilesystem true, runAsNonRoot true, capabilities.drop ALL and seccompProfile RuntimeDefault.
- `kubectl` is in the runner image, but the runner pod holds no cluster token and no route to the cluster, so `devops k8s searxng-check` and the real `push-secrets` are NOT_IN_RUNNER: a person runs them from the workstation. The `charts` row needs docker and helm, which are NOT_IN_RUNNER, so no step names it.
- The scope comment of 2026-11-12 lists an alert on `searxng_engines_reliability_total`; this change adds no rule, because the issue's acceptance criteria hold none, the series name and the threshold are unverified until the first scrape, and #6753 reads the series first.

## Existing Tool Considered

searxng/searxng (AGPL-3.0, maintained, last activity 2026-11-19): its OpenMetrics endpoint at `/metrics` exposes each engine's request, error and reliability counts behind basic auth, so this change enables `general.open_metrics` and scrapes that endpoint. The change adopts that tool and builds no replacement: the render is one init container of a few shell lines, about 15k tokens to build, about 2k tokens a month to keep and fix, and about 3 hours of elapsed time.

## Dependencies

- devops_cli_web_searches_total: the metric name of the issue also sits in docs/CLUSTER.md, docs/TELEMETRY.md, k8s/devops/monitoring/prometheus-rules-values.yaml, src/devops_cli/ai/web_search.py, src/devops_cli/config/constants.py, src/devops_cli/telemetry/instruments.py, tests/ai/test_web_search.py, tests/fixtures/prometheus_rules/, openspec/specs/roadmap-alternatives/spec.md, openspec/specs/roadmap-service-alerts/spec.md, openspec/specs/web-search/spec.md, the open change folder of #4141 and the archives of #3893, #3925 and #4044; this change adds no label to the metric and changes none of those files.
- Open item #4141 edits `k8s/devops/searxng/configmap.yaml` in its own change folder, so its engine-set edit lands before group 3 adds the `general` block to the same file.
- Open item #5093 bumps the SearXNG image pin in `k8s/devops/searxng/deployment.yaml`, the file that group 4 edits, so the two merge in one order and the init container keeps the pin.
- Open item #6727 changes the `searxng-service` spec that this change modifies, so one of the two rebases on the other.

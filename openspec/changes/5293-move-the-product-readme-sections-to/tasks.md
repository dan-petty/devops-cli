# Tasks

## 1. The readers of the product sections

- [x] 1.1 Re-point the tests that read the moved sections to `docs/CLUSTER.md`: `tests/prometheus/test_k8s_monitoring_alerting.py` (the sections "Roadmap service" and "Crawl4AI", the row of `RoadmapServiceGitHubRequestsHigh` and the expected pointers), `tests/server/routes/test_k8s_roadmap_service.py` (the subsection Webhook route), `tests/invariants/test_runner_image.py`, `tests/invariants/test_k8s_searxng.py`, `tests/roadmap/implement/test_roadmap_implement_deadline_settings.py`, `tests/invariants/test_configmap_rollout_rule.py`, and `tests/roadmap/test_roadmap_step_rules.py` (a manifest group gets "Image Pins" of `docs/CLUSTER.md`). Add `docs/CLUSTER.md` to the agent instruction files of `tests/invariants/test_agents_md.py`. The tests fail while `docs/CLUSTER.md` is missing.
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py tests/server/routes/test_k8s_roadmap_service.py tests/invariants/test_runner_image.py tests/invariants/test_k8s_searxng.py tests/roadmap/implement/test_roadmap_implement_deadline_settings.py tests/invariants/test_configmap_rollout_rule.py tests/roadmap/test_roadmap_step_rules.py`
- [ ] 1.2 Add the route of `k8s/**` to the section "Image Pins" of `docs/CLUSTER.md` in `src/devops_cli/roadmap/step_rules.py`, and remove "Image Pins" from the route to `k8s/README.md`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_step_rules.py tests/invariants/test_agents_md.py`

## 2. The move

- [ ] 2.1 Move "devops-cli in the cluster" (less "Agent sessions"), "Image Pins" and "Service Image Updates" from `k8s/README.md` to `docs/CLUSTER.md`, one heading level higher. Link the environment sections of `k8s/README.md` from the moved text, and link `docs/CLUSTER.md` from the references that stay in `k8s/README.md`.
  - Verification: `$ uv run devops ci test tests/docs/test_docs_inventory.py tests/invariants/test_agents_md.py`
- [ ] 2.2 Re-point the alert descriptions of `k8s/monitoring/prometheus-values.yaml` and the expected descriptions of `tests/fixtures/prometheus_rules/` to `(docs/CLUSTER.md, Roadmap service)` and `(docs/CLUSTER.md, Crawl4AI)`.
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`
  - Verification: `$ ! git grep -n -F 'k8s/README.md, Roadmap service' -- k8s src docs .github tests/prometheus tests/fixtures/prometheus_rules`
  - Verification: `$ ! git grep -n -F 'k8s/README.md, Crawl4AI' -- k8s src docs .github tests/prometheus tests/fixtures/prometheus_rules`
- [ ] 2.3 Re-point the other references: the comments of `k8s/devops/`, `.github/renovate.json`, `CONTEXT.md`, `CONTRIBUTING.md`, `RELEASE_CYCLE.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/ROUTINE_TASKS.md`, `docs/roadmap/implement.md`, `src/devops_cli/config/defaults.py` and the test docstrings.
  - Verification: `$ ! git grep -n -F 'README.md#crawl4ai' -- CONTRIBUTING.md docs`
  - Verification: `$ ! git grep -n -F 'k8s/README.md#go-live-check' -- docs`
- [ ] 2.4 Compare the renders of the touched k8s paths at `origin/main` and on the branch: `kubectl kustomize` of `k8s/devops`, `k8s/overlays/homelab/devops` and `k8s/monitoring` gives the same output, and `helm template` of chart `prometheus` 29.47.2 with `k8s/monitoring/prometheus-values.yaml` differs only in the 21 descriptions.

## 3. Documents

- [ ] 3.1 Link `docs/CLUSTER.md` in the row "change a manifest, the cluster or OpenTofu" of `AGENTS.md` within its character cap, add it to the Guides tab of `.nav.yml` and to `docs/index.md`, and build the docs site.
  - Verification: `$ uv run --group docs devops docs site build --strict`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

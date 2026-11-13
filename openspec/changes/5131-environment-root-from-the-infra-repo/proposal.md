# Proposal: #5131

## Why

#5131 (step 4 of the corrected plan on #5120): the environment tree of the homelab must move from devops-cli to the infra repo dan-petty/homelab (#5134). The product reads the tree at fixed paths of this repository: `DEFAULT_K8S_DIR`, the paths that `stack_lifecycle.py` joins to it at import time, `CONST_K8S_ARGOCD_APPLICATION_DIRS`, `CONST_K8S_OLLAMA_PROFILES_PATH`, the `DEFAULT_LLM_*` paths, `DEFAULT_GRAFANA_DASHBOARDS_DIRS`, the path of `ollama prune` and the path defaults of `argo.py`. Names of live objects are constants too: `CONST_K8S_ARGOCD_PAUSE_PARENTS`, `CONST_K8S_GITEA_APPLICATIONS`, the team default `homelab` and the Cloudflare Access names. `devops k8s image-pins` and the Argo CD gate also map every `$ref` and every path source to the local checkout, so they cannot check a tree whose Application `devops` names devops-cli and whose Application `prometheus` has a second ref on devops-cli. Closes #5131.

## What Changes

- New module `devops_cli.k8s.environment`: the `EnvironmentTree` (its root, the repository that holds it, and the paths that devops reads in it) and `resolve_environment`. The root comes from `--k8s-dir`, else from the profile fact `kubernetes.dir` of the repository of the current folder, else from the one entry of `infra.repos` whose checkout gives it. `resolve_product_root` gives the product base `k8s/devops` (`--product-dir`).
- `.devops/project.toml` of devops-cli declares `[kubernetes] dir = "k8s"`, so each command reads the same tree as before in a checkout of devops-cli. After the switch (#5134), the removal of this line moves every command to the tree of the infra repo.
- `deploy-stack`, `teardown-stack`, `bootstrap`, `image-pins`, `lint`, `check-deprecated`, `ollama prune`, `devops grafana dashboards sync` and `lint`, `devops ai gateway render`, `devops argo cd apps bootstrap-gitops` and `devops argo gitops watch` and `drift` read the tree. `deploy-stack` and `teardown-stack` take `--product-dir`; `image-pins`, `ollama prune`, `dashboards` and `gateway render` take `--k8s-dir`. The stack tables hold paths relative to the tree, and the product paths are in `PRODUCT_MANIFESTS_BY_STACK`, `PRODUCT_POST_HELM_BY_STACK` and the `product_values` of a release (the alert rules that #5292 moved to `k8s/devops/monitoring/`). With no folder, `devops grafana dashboards sync` and `lint` read `monitoring/dashboards` of the tree, then `dashboards` of the product base when the current repository holds it.
- New module `devops_cli.k8s.app_sources`: a git source of the origin reads the checkout, and a source of another `https` repository is fetched once at its `targetRevision`. A `$<ref>/<path>` value file names the folder of the source with that ref. `image-pins` and `check_argocd_gate` use it. `image-pins <folder>` renders one kustomization folder, such as `k8s/devops`.
- New settings: `argocd.root_applications`, `gitea.applications`, `mattermost.team`, and `cloudflare.access.application_name`, `allow_policy_name` and `bypass_policy_name`. Their defaults are the names of the live objects of today.
- The constants listed in Why are deleted. `CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS` stays, because #5134 step 5c deletes it.
- `tests/support/k8s_tree.py` reads a value file of any ref name, and gives `TREE`, the environment tree of this repository.
- The dead design-token filter `k8s/startpage/**` leaves `ci.yml` and `DESIGN_FILTER`.
- Spec deltas: options, defaults, messages and the fetch are behavior that a person sees, so the change carries deltas for `k8s-environment-root` (new), `k8s-image-pins`, `mattermost-bootstrap` and `local-path-volume-placement`.

## Capabilities

- `k8s-environment-root` (new): where the tree comes from, the commands that read it, the product base, and the settings that name live objects.
- `k8s-image-pins`: the sources of another repository, the kustomization folder, the environment tree, and the paths of the CI job.
- `mattermost-bootstrap`: the default team is a setting.
- `local-path-volume-placement`: the root Applications that a volume move pauses are a setting.

## Impact

The readers of `k8s/` after this change:

- **Stays in devops-cli:** `tests/invariants/test_k8s_crawl4ai.py` and `tests/invariants/test_k8s_searxng.py` (they read the product base through `PRODUCT_MANIFESTS_BY_STACK`), `third-party-image-scan.yml`, the promtool step of `ci.yml`, `trivy config`, the Renovate kubernetes manager scoped to `^k8s/devops/` (#5134), `image-pins.yml` (scoped to `k8s/devops/**` with the folder mode by #5134 step 6), the roadmap stage paths (`stage_paths.py`, `stage_change.py`, `step_rules.py`, `stage_context_facts.py`) and `research/k8s_pins.py`, which describe the layout of the repository that a job changes and not the environment tree. The cloudflared and README checks of the two test files change in #5296 and #5293.
- **Moves to dan-petty/homelab** (#5296): `tests/invariants/test_k8s_argocd_apps.py`, the manifest part of `tests/invariants/test_k8s_manifests.py`, the `k8s` row of `devops ci`, the environment alert and dashboard tests, the cloudflared checks, and the other k8s managers of `.github/renovate.json`. `sre-service.json` and `llm-stack.json` are environment dashboards. These tests read the tree through `tests/support/k8s_tree.py` (`TREE`) now, so one root changes when they move.
- **Deleted:** the dead design-token filter `k8s/startpage/**` of `ci.yml` and of `DESIGN_FILTER`. `k8s/monitoring/dashboards/**` stays in the filter, because `make dashboards` writes there since #5280. The cross-repo pin tests go with #5134.
- **Product contracts on a fixture tree:** #5298 (the old item 4 of #5131).

No file moves. A consumer of devops-cli outside this repository passes `--k8s-dir` or declares `kubernetes.dir` in `.devops/project.toml`. The change fits one pull request.

## Feasibility

Checked against origin/main `f9ca1b4de` (devops-cli 0.125.0), and again after the rebase onto `ca5dfa5c5`, which holds #5292 (the product dashboards and rules in `k8s/devops/`, the values list of `StackRelease`, and `DEFAULT_GRAFANA_DASHBOARDS_DIRS`):

- `src/devops_cli/project/profile.py:63-68` has `KubernetesProfile.dir`, and detection gives `k8s` for a repository with `ansible.cfg` and a `k8s` folder (`profile.py:180`). `InfraRepoConfig` has `extra="forbid"` (`settings.py:1584`), so the fact comes from the profile and not from a new key of `infra.repos`. `infra/onboard.py:85-87` gives the default checkout of an infra repo.
- `git grep` of the 13 constant names of Why in `src/` gives 127 lines in 14 files on `f9ca1b4de` and 0 on the branch. `DEFAULT_K8S_DIR` alone gives 73 lines (68 in `stack_lifecycle.py`).
- `image_pins.py:183-185` maps every `$<ref>` to the local root, and `:244-245` builds each path source from the local root. `argocd_gate.py:229-234` refuses a git source that is not the origin. `tests/support/k8s_tree.py:17,75` strips only `$values/`.
- `render_at_revision` (`argocd_overrides.py:85-113`) already fetches one revision with `git init`, `git fetch --depth 1 --end-of-options` and a checkout of `FETCH_HEAD`; the new fetch uses the same commands. A private repository is #5294.
- `git ls-files k8s/startpage` gives no file, so the filter `k8s/startpage/**` is dead. `make dashboards` (Makefile:22-23) writes `k8s/monitoring/dashboards/`, so that filter stays.
- The final plan of #5120 lists the roadmap stage paths under "stays": they name the layout of the repository that a job changes. The body of #5131 lists them in item 1; this change follows the plan.
- `tests/core/test_git_contract.py::...[review_window]` fails on origin/main without this change too.

## Existing Tool Considered

Kustomize remote bases and `helm` cover a render of another repository, but `image-pins` and the gate must render each source as Argo CD does and name the Application of each image, so they keep their render and fetch the source with git, as `render_at_revision` does. The settings system covers the names. The work is to remove fixed paths, with no new dependency. Cost, from the issue: about 6M tokens to build, 0.5M a quarter to keep, 8 hours; the foreign-source support adds about 2M tokens and 3 hours. The change deletes `DEFAULT_K8S_DIR`, `CONST_K8S_ARGOCD_APPLICATION_DIRS`, `CONST_K8S_ARGOCD_PAUSE_PARENTS`, `CONST_K8S_GITEA_APPLICATIONS`, `CONST_K8S_OLLAMA_PROFILES_PATH`, `DEFAULT_GRAFANA_DASHBOARDS_DIRS`, the five `DEFAULT_LLM_*_PATH` constants, the two Cloudflare policy constants, and the private `_normalize_git_url`, `_get_repo_origin` and `_value_file`.

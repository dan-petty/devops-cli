# Design

## Decisions

### The decision of each allow-listed test of the area
The allow list held 141 tests of the area. Each one is deleted, replaced by a test of source code on a fixture, or kept.

| Group | Tests | Decision | Reason |
| --- | --- | --- | --- |
| `tests/k8s/test_k8s_cluster_job_api.py`, `tests/k8s/test_k8s_cluster_job.py` | 32 + 5 | replace | `build_job` and `ClusterJobs` read the CronJob from the cluster at run time. `tests/support/job_templates.py` builds a CronJob in the shape of each template, so no value of `k8s/devops/cronjob-*.yaml` reaches a test. |
| `tests/k8s/test_k8s_configmap_keys.py` | 4 | replace | Three tests give `unknown_setting_keys` a mapping that they build. The check of the committed template moves into the render (`render_devops_configmap_content`), which a deploy runs, and `tests/k8s/test_k8s_configmap.py` tests the refusal on a fixture template. |
| `tests/commands/k8s/test_k8s.py`: the values order of `prometheus`, the native ConfigMap apply, the teardown of the CRD release | 3 | replace | deploy-stack reads the Applications and the values paths at run time. The values order is a dry run on a tree that the test writes, with a second test for a release that no Application pins. The two other tests keep the assert of the code and lose the asserts of committed file names and of the CRD keep annotation. |
| `tests/invariants/test_k8s_argocd_apps.py`: the chart sources and the deploy-stack counterpart of each Application | 2 | replace | `chart_versions` (`tests/k8s/test_app_sources.py`) and the dry run on a written tree test the code that reads the Applications. That a file of the tree is in both install paths is the work of the `k8s` row and of a deploy. |
| `tests/commands/k8s/test_k8s_gpu_placement.py` | 1 | replace | deploy-stack reads the Ollama profiles at run time. The test writes a profile with one tier that needs an architecture. |
| `tests/commands/k8s/test_k8s_agents_manifests.py`: the audit of the agents binding | 1 | replace | `audit_rbac` gets a binding that the test builds. `devops k8s rbac-audit` audits the live bindings. |
| `tests/commands/k8s/test_k8s_devops_stack.py` | 1 | replace | The order rule (the rate limit before the Ingress) is a rule of the source table and stays as its own test. The existence of the files is the work of a deploy and of the `k8s` row. |
| `tests/invariants/test_k8s_manifests.py::test_readme_lists_the_table` | 1 | keep | It compares the README table, a document, with `CLUSTER_SECRETS` and asserts no value of a manifest. The guard counted it only through the part `REPO_ROOT / "k8s"` of the path; the guard now judges a path whole. |
| Namespaces, security contexts, Pod Security, tokens, RBAC, perimeters and NetworkPolicies, prune protection, finalizers, secret references, chart values, image and chart pins, nested timeouts, notifier keys, no leaked identity, Valkey memory bounds, Mattermost, Gitea, Qdrant, Tempo, logging, gateway config, the devops runtime CronJob, Crawl4AI, SearXNG and Renovate manifests | 91 | delete | Each asserts a value of a manifest, of a chart values file or of a config file (#6060, owner decision of 2026-11-17). kube-linter, the `k8s` row, `trivy config` and the live checks cover the controls. |

The tests of the same modules that read the tree through the readers of `tests.support.k8s_tree`, which the guard did not count, go with them: 2 of Crawl4AI, 1 of GPU feature discovery, 5 of the MCP server policies, 10 of the token gate, the secret table guard and the routes in `tests/invariants/test_k8s_manifests.py`, 7 of Renovate, 8 of SearXNG (with `tests/fixtures/searxng/engines_that_never_answer.txt`) and the 4 of `tests/core/test_k8s_local_path_placement.py`. The tests of the helpers of those tests go too: 5 in `test_k8s_manifests.py` and 11 in `test_k8s_local_path_placement.py`. `test_loki_deletes_logs_once_they_are_thirty_days_old` read `k8s/logging/loki-values.yaml` through `REPO_ROOT.joinpath(*parts)`, which the guard does not see, and goes too.

### The guard counts the readers of the tree and judges a path whole
The readers of `tests.support.k8s_tree` (`manifests`, `chart_values` and the others) read `k8s/`, but the guard counted only the names `K8S`, `TREE` and `APPLICATIONS`. The guard now counts a call of a reader. Only this area used them, so no module outside the area gets a count. The guard also walked into the part `REPO_ROOT / "k8s"` of a longer path, and counted a Markdown document under a config folder as a read. It now skips the inner part of a path, so the two tests of `tests/invariants/test_pull_request_template.py` leave the list too.

### The render refuses an unknown key
`unknown_setting_keys` had no caller but the test of the committed template. The render of the ConfigMap now calls it after the validation of the settings, so a deploy stops on a template key that a change removed from the settings. The committed template renders with no unknown key.

### Specs
A scenario whose proof was a deleted test now names a validator command or a live check, as `openspec/config.yaml` asks. A MODIFIED block cannot drop a scenario, so a requirement whose scenarios described the test itself (the Loki mode helper) goes, and a requirement with a new title holds its rule. Two requirements described a check of the deleted test (the token check, the secret reference guard) and go.

#6120 (#6118) changed the same capabilities first: it gave most scenarios a command proof, removed the requirements that only restate a file, and gave new titles to the token gate and the claim placement requirements. This change keeps each requirement that #6120 changed or removed. Its deltas change only the requirements that #6120 left as they were and whose scenario names a deleted test. No scenario names `kubectl exec`.

## Rejected alternatives
- Move the deleted rules to rows of the `k8s` gate: the owner rule asks for no check of a manifest value, and the tools of CI (kube-linter #6068, kubeconform, `trivy config`) and the live checks are the place of these controls.
- Keep the SearXNG engine review and the claim placement tests as review gates: after the guard counts the readers of the tree, they are value tests on the allow list, which #6082 takes to zero. `devops k8s searxng-check` checks the engines that must stay off on the running service.
- Count `REPO_ROOT.joinpath(*parts)` and the support modules that read `k8s/` in the guard in this change: the forms are in modules of other areas (`tests/core/test_renovate_config.py`, `tests/support/fakes/cluster_jobs.py`), so each area pull request decides them.

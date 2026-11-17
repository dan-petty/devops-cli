# Proposal: #6118

## Why
About 330 scenarios of the living specs say "a test reads <manifest or config file>". The owner rule of 2026-11-16 (#6060) removes each test that asserts a value of a manifest or a config file, and #6075 and #6082 delete those tests. The stage and refine jobs read the living specs and copy their form, so these scenarios keep plans that ask for value tests. #6080 changed the rule for a new scenario: a scenario of a manifest, a workflow or a config file names a validator command or a live check as its proof. This change rewrites the scenarios of the first area, Kubernetes, the cluster and the stacks, in that form. Closes #6118, the sub-issue of this area. Part of #6083: more areas follow, one sub-issue for each area.

## What Changes
- In 19 capabilities, each scenario that read a manifest now names one of these proofs:
  - `uv run devops ci --check --only k8s`, where a check of `tests/gate/k8s_checks` holds the rule;
  - a live check of the cluster: a throwaway pod that runs `nc -w 3` (started with `kubectl run`), `kubectl auth can-i`, `kubectl rollout status`, `kubectl get`, `uv run devops k8s searxng-check`, `uv run devops k8s crawl4ai-check`, `uv run devops prometheus rules` or `uv run devops prometheus query`;
  - a validator: `uv run devops k8s image-pins`, `uv run devops k8s lint`, `uv run devops scan secrets`, `uv run devops grafana dashboards lint`;
  - the dry run of a devops command: `uv run devops k8s deploy-stack --dry-run` or `uv run devops k8s push-secrets --dry-run`.
- A requirement that only restates a value of a file goes: a document that repeats a table or a list, a comment of a manifest, the example ConfigMap, the text of an alert, the license text of three documents (10 requirements).
- A requirement whose scenario name says "A test reads" goes out as REMOVED and comes back as ADDED under a new name with the same rule, because OpenSpec keeps each scenario name of a MODIFIED requirement (20 requirements). The new text of the Gitea chart and image drops the version and the tag that Renovate updates.
- A scenario that reads a table of the source code, which a test of the source code covers, stays: the cluster secret table, `OPTIONAL_FEATURE_SECRETS` and the deploy-stack tables.
- No code and no test changes.

## Capabilities
- `k8s-network-policies`: 6 modified, 1 removed.
- `k8s-helm-deploy`: 3 modified.
- `k8s-gvisor-runtime`: 2 modified.
- `k8s-planner-run-job`: 2 modified.
- `cluster-image-registry`: 1 modified, 1 removed and added again.
- `gitops-host-overrides`: 2 removed and added again.
- `homelab-project-destinations`: 2 removed and added again.
- `service-account-tokens`: 1 removed and added again.
- `local-path-volume-placement`: 1 modified, 1 removed and added again.
- `searxng-service`: 8 modified, 3 removed.
- `renovate-service`: 9 modified, 1 removed, 1 removed and added again.
- `crawl4ai-service`: 6 modified.
- `crawl4ai-api-token`: 1 removed.
- `crawl4ai-alerts`: 1 modified, 1 removed.
- `gitea-forge`: 11 removed and added again.
- `llm-gateway-database`: 11 modified.
- `grafana-image-renderer`: 5 modified.
- `qdrant-read-only-key`: 2 modified, 2 removed.
- `cloudflared-tunnel-availability`: 2 modified.

## Impact
- Census `git grep -c -i "a test reads" -- openspec/specs`: the 19 capabilities fall from 125 to 9 hits, and all specs fall from 334 to 218. Each hit left in the area reads a table of the source code that a test covers.
- No user, command or service changes. The stage and refine jobs read the new scenarios as examples of the proof form.

## Feasibility
- Each command that a scenario names exists: `devops k8s image-pins`, `lint`, `searxng-check`, `crawl4ai-check`, `deploy-stack --dry-run`, `push-secrets --dry-run`, `devops prometheus rules` and `query`, `devops scan secrets`, `devops grafana dashboards lint` and `search --query`, `devops gh pr checks`.
- Each gate check that a `k8s` scenario names exists in `tests/gate/k8s_checks`, and the guard of #6075 (`config_reads.toml`) counts only pytest modules, so #6082 does not delete these checks.
- The dry run of `deploy-stack --stack infra` lists `cloudnative-pg` and `cert-manager` before `plugin-barman-cloud`, both in namespace `cnpg-system`, and the dry run of `push-secrets --stack devops` names the keyring entry of each key.
- `devops k8s lint` passes on `k8s/devops/searxng`, `k8s/devops/crawl4ai` and `k8s/cloudflared`. On `k8s/devops/renovate` it reports only `job-ttl-seconds-after-finished` and `latest-tag`, so the Renovate scenario names the checks of Pod Security.
- Namespaces `devops` and `gitea` enforce Pod Security `restricted` (`k8s/namespaces.yaml`), so the API server refuses a pod that breaks that level.

## Existing Tool Considered
- OpenSpec deltas and `openspec archive` apply the rewrite, and the validators are the tools that the cluster and the repository already run: the `k8s` gate row, Kube-linter, Pod Security admission, Prometheus, kubectl and Gitleaks. No new tool. Cost: about 1.5M agent tokens and 3 hours.

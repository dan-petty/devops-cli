# Proposal: #7290

## Why

#7290 is step 17 of `docs/HOMELAB_REPO_SWITCH.md`. Since step 11, Argo CD reads the environment of the cluster from dan-petty/homelab, so each environment file under `k8s/` of devops-cli is a stale copy. A person or an agent can read, edit or apply it. The owner wants one place for each resource.

## What Changes

- devops-cli holds no environment file. Under `k8s/`, git tracks the product base `k8s/devops/` and Markdown documents only. A check of the `k8s` row holds this.
- `.devops/project.toml` declares no `kubernetes.dir`. A command that reads the environment tree takes it from `--k8s-dir` or `infra.repos`.
- No fallback: the cluster Secret table reads no file of `tests/fixtures/`.
- A command that needs a file or folder of the tree that the tree does not hold stops with a `ConfigurationError` that names the path, `--k8s-dir` and `infra.repos`. No command reports success on an empty tree. `k8s lint` fails on a folder with no object, and `k8s image-pins` fails when the renders name no image.
- `devops k8s bootstrap-mattermost` gets `--k8s-dir`.
- `deploy-stack` and `teardown-stack` refuse a tree that lacks a path of a selected stack. The stack `llm` names the folder `llm/valkey`, which the environment repository holds in place of `llm/valkey.yaml`.
- `devops argo gitops drift` and `watch --once` refuse a watched path with no manifest and no change. `devops k8s catalog` says when the tree has no SLO folder.
- `devops repos onboard` deploys only with an environment tree whose checkout is clean at its `origin/main`, and gives that tree to each child command.
- The `kube-linter` row lints `k8s/devops`. The `k8s` row, `image-pins.yml` and the third-party image scan read product files only.
- The `charts` row, the freeze check of step 12, the environment gate checks and their fixtures are deleted. Renovate of devops-cli has no manager or rule for an environment file.

This change alters commands and manifests, so it has spec deltas.

It is one pull request: the deletion, the commands that read the deleted files, the checks and the documents break `main` when they merge apart.

## Capabilities

- Environment behavior: `k8s-environment-root`, `cluster-secrets-loader`, `k8s-lint`, `k8s-image-pins`, `grafana-dashboard-lint`, `mattermost-bootstrap`, `repos-onboard`, `k8s-helm-deploy`, `gitea-forge`, `ai-gateway-routing`.
- Checks and workflows: `ci-gate-rows`, `ci-fail-to-pass`, `test-ratchets`, `crawl4ai-service`, `release-concurrency-and-renovate`.
- A requirement that states a value of a deleted file is removed. A capability with no requirement left is retired (`retire_capabilities: true`). A product requirement of a retired capability moves to `ci-gate-rows`, `cluster-secrets-loader`, `k8s-helm-deploy` or `service-dashboard-template`.
- The other capabilities of `specs/` change only where a requirement or a scenario names a deleted file.

## Impact

- A command of the environment tree that runs in a checkout of devops-cli needs `--k8s-dir` or `infra.repos`.
- `devops ci --only charts` is a usage error.
- `devops research sweep` of devops-cli sees no chart pin and no image pin of the environment.
- The revert of the switch is no longer possible.
- Checks that only the environment repository can do now: the gateway config against the model names and prices of the CLI, the privacy rules of the gateway and the Collector, the rule that only the tunnel reaches Traefik, the Tempo query limits and the alert rules of the environment.
- The open changes #4530 and #4576 add requirements to capabilities that this change retires, and #2144 and #4600 plan work on deleted files.

## Feasibility

- `docs/HOMELAB_REPO_SWITCH.md` step 11 records the switch of the Argo CD sources to dan-petty/homelab. Step 16 adds the environment checks there. The same page records that the owner waived the 7 day condition of step 17 on 2026-11-26.
- `git ls-files k8s` in the branch lists files of `k8s/devops/` and Markdown documents only.
- Before this change, `load_cluster_secrets_table` of `src/devops_cli/k8s/cluster_secrets.py` read `tests/fixtures/cluster-secrets.toml` when the tree had no `cluster-secrets.toml`, so product code took rows from test data.
- Pending before the merge, by a person: shared check 7 of the runbook on the live cluster, which shows that no live source names a deleted path.

## Existing Tool Considered

- This change deletes files and code. It needs no new library.
- Argo CD, kube-linter and kustomize stay the tools of the product base. `--fail-if-no-objects-found` of kube-linter gives the failure on an empty folder, so devops-cli counts no object itself.
- The structure check is one gate module of a few lines over `git ls-files`. A `fail` hook of pre-commit covers the same paths, but the CI gate runs no such hook. The cost of the module is a few thousand tokens and some minutes.
- Internal code deleted: `tests/gate/charts.py`, `charts_render.py` and `charts_checks/`, the gate modules `environment_freeze`, `argocd_apps`, `argo_workflows`, `gateway_database`, `monitoring`, `object_store`, `object_store_buckets`, `ollama_service`, `otel_collector`, `otel_endpoints` and `valkey_memory`, the freeze test, the OTLP endpoint test and the fixture fallback of the Secret table.

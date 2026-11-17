# Proposal: #6060

## Why
Tests repeat the values of manifests and config files: chart versions, image tags and digests, model names, limits, ports, keys and table rows. When Renovate updates a pin, these tests fail although no project code changed. On 2026-11-16 the Renovate pull requests #6046 and #6029 failed on such tests. The owner widened the item the same day: "I don't want any tests that check that a manifest or config has any particular value. They should be testing the source code of the project", "we shouldn't create unit tests for things that are better measured with end to end and integration tests", and "remove any tests or workflows that will block renovate updates". Closes #6060.

## What Changes
- Delete each test, or the part of a test, that reads a committed manifest, ConfigMap template, gateway or Renovate config, workflow, Dockerfile or other config file and asserts a value in it. Delete the fixtures, support helpers and dead code that only those tests used.
- `devops k8s deploy-stack` reads the version of each chart from the Argo CD Application of the environment tree. `HELM_RELEASES_BY_STACK` holds no version, so a pin has one place, and a Renovate update of an Application moves both install paths. A release that no Application pins stops the deploy with an error that names the release.
- `CRAWL4AI_IMAGE` and the `k8s` gate assert that held the Crawl4AI image to it go. A Crawl4AI image updates like any other image.
- Tests that read a committed file and hold a safety rule, or agree code with a manifest at run time, stay unchanged as gray cases for the owner. The pull request lists them with a proposed decision.
- A new check of the `test-tree` row refuses a new test that reads a committed manifest or config file. `tests/gate/tree_checks/config_reads.toml` holds the count of such tests of each module, and the count only falls.
- `docs/TESTING.md` states the two rules: a test checks project source code and asserts no value of a manifest or config, and a behavior that spans components is measured at the real edge or at a fake that keeps its contract (ADR 0007).
- Documents and specs that named a deleted test or a pinned version are corrected.

## Capabilities
- `k8s-helm-deploy`: modified (the version comes from the Application of the tree).
- `k8s-crawl4ai-check`: the requirement "Pinned image" is removed.
- `ollama-model-prune`: the requirement "The written keep set matches the gateway config" is removed.
- `roadmap-eval-implement`: the requirement "The Harbor version is pinned" is removed.
- `loki-patterns`, `dcgm-exporter`, `llm-stack-dashboard`, `gitops-host-overrides`, `otel-collector-alerts`: modified (no pinned version, no deleted capture).
- `test-ratchets`: a requirement for the tests that read committed config is added.
- `workload-rollout`: modified (the scenarios name a live `kubectl` check, not a test that reads a manifest).
- `release-concurrency-and-renovate`: modified (a chart update is a fix because deploy-stack reads the version from the Application).

## Impact
- Tests: about 700 test functions and 8 test files go; the count of the tests, the test lines and the run time of `Tests & Coverage` fall.
- Code: `src/devops_cli/commands/k8s/stack_lifecycle.py`, `src/devops_cli/k8s/app_sources.py`, `src/devops_cli/k8s/crawl4ai_check.py`, `src/devops_cli/commands/scan.py` (dead code), the error and message texts.
- A Renovate pull request that updates a pin needs no test change, except for the gray cases until the owner decides them and the SearXNG gate and the token tables, which the pull request of the Renovate fixer removes.

## Feasibility
- A simulated Renovate patch bump of every chart `targetRevision`, image tag and digest under `k8s/`, `Dockerfile` and `.devcontainer/` failed 12 tests and one `k8s` gate case before this change. After it, only the SearXNG and token-table cases fail, which the Renovate fixer removes.
- `deploy-stack` already resolves each values file in the environment tree; the Applications of the tree name `chart` and `targetRevision` for each release.

## Existing Tool Considered
- Renovate updates the pins, and the CI validators (`kubectl kustomize`, `trivy config`, kube-linter, kubeconform, `actionlint`, `zizmor`, `promtool`) check the form of the files. The guard is a small check of the existing `test-tree` row, the place of the other test-tree rules. Cost: about 2M agent tokens and 5 hours.

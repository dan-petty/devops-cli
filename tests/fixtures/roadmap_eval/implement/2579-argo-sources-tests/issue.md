## Problem Description

`devops argo cd apps list` shows an empty Repo column for every Application that uses `spec.sources` (multi-source) in place of `spec.source`. `ArgoAppInfo` reads `spec.source.repoURL` only (`src/devops_cli/models/argo.py`), and a multi-source Application has no `spec.source`.

On the homelab (2026-10-29), 16 of the 29 Applications use `spec.sources`, for example `argocd` (chart, values ref and git), and `grafana`, `loki`, `traefik` and `argo-workflows` (chart and values ref). All 16 show no repository.

## Reproduction Steps

1. Have an Argo CD Application with `spec.sources` (for example a Helm chart source and a `ref` source for its values).
2. Run `uv run devops argo cd apps list`.

## Expected vs Actual Behavior

- Expected: the Repo column names each source of the Application (for example the chart repository and the values repository), or the first source, with a rule the help states.
- Actual: the Repo column is empty.

## Environment Diagnostics

origin/main `cabfcd43`. Read-only `kubectl -n argocd get applications -o json` shows `spec.source` unset and `spec.sources` set on each of the 16.

## Logs, Traces, or Terminal Output

`devops argo cd apps list`: `argocd`, `argo-workflows`, `argocd-image-updater`, `dcgm-exporter`, `gitea`, `grafana`, `k8s-monitoring`, `loki`, `open-webui`, `otel-collector`, `prometheus`, `prometheus-operator-crds`, `pyroscope`, `qdrant`, `tempo` and `traefik` show no repository. The single-source Applications (`base`, `devops`, `llm` and others) show theirs.

## Existing Tool Considered

The Argo CD Application spec defines `spec.sources` as a list of the same source objects. The fix reads it in the existing model. Nothing new is built.

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=07fb4c222b09ef6bb9e6fc9cd1d5fbb45f6c9a78 -->
## Proposed design

### Problem statement
The command `devops argo cd apps list` shows an empty Repo column for every Argo CD Application that uses `spec.sources` (multi-source) instead of `spec.source`. The model reads only `spec.source.repoURL`. On the homelab, 16 of 29 Applications use `spec.sources` and all show no repository. The fix reads `spec.sources[0].repoURL` as a fallback in the existing model.

### Acceptance criteria

### Requirement: Single-source repo shown
When an Application has `spec.source.repoURL`, the Repo column SHALL show that URL.

#### Scenario: Application with spec.source set
- **WHEN** An Application JSON has `spec.source.repoURL` set to a value and `spec.sources` absent
- **THEN** The Repo column shows the value of `spec.source.repoURL`

### Requirement: Multi-source first repo shown
When an Application has `spec.sources` and no `spec.source`, the Repo column SHALL show the `repoURL` of the first element of `spec.sources`.

#### Scenario: Application with spec.sources list
- **WHEN** An Application JSON has `spec.sources` as a non-empty list and `spec.source` absent
- **THEN** The Repo column shows the `repoURL` of `spec.sources[0]`

### Requirement: No source yields empty repo
When an Application has neither `spec.source` nor `spec.sources`, the Repo column SHALL be empty.

#### Scenario: Application with no source fields
- **WHEN** An Application JSON has neither `spec.source` nor `spec.sources`
- **THEN** The Repo column is an empty string

### Existing Tool Considered
No check has run. No external tool covers this need because it is a bug in the project's own model code. The fix adds a fallback read of `spec.sources[0].repoURL` in `src/devops_cli/models/argo.py`. The written cost is a few lines of code to build, keep and fix, well under one hour of elapsed time.

### Key questions
- **What value to show in the Repo column for a multi-source Application?**: Show the `repoURL` of the first element of `spec.sources`. This matches the Argo CD CLI behavior and keeps the column narrow and predictable. (best practice) [sources: src/devops_cli/models/argo.py]
  - Chosen: First source repoURL. Matches Argo CD CLI behavior. Keeps the column narrow. The first source is the primary source by Argo CD convention.
  - Rejected: All repoURLs joined by comma. Shows every source but makes the column very wide and hard to read in a table.
  - Rejected: Leave empty. Preserves the current broken behavior. Does not fix the issue.
- **Which methods in the model need the fallback read?**: Two methods: `ArgoCDApp.from_api_item` and `ArgoResourceState.from_manifest`, both in `src/devops_cli/models/argo.py`. Both currently read only `spec.source.repoURL`. [sources: src/devops_cli/models/argo.py:40, src/devops_cli/models/argo.py:155]

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->

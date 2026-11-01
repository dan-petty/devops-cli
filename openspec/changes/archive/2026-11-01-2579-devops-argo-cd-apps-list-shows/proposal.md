# Proposal

## Why

#2579 reports that devops argo cd apps list shows an empty Repo column for every Application that uses spec.sources (multi-source) in place of spec.source. The model reads only spec.source.repoURL, so 16 of 29 homelab Applications show no repository.

## What Changes

- ArgoCDApp.from_api_item falls back to spec.sources[0].repoURL when spec.source is absent.
- ArgoResourceState.from_manifest falls back to spec.sources[0].repoURL when spec.source is absent.
- Tests assert the fallback for both methods and the empty-string case when neither field is set.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `argo-cd-apps-list`: single-source-repo-shown, multi-source-first-repo-shown, no-source-empty-repo

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/models/argo.py`
- Tests: `tests/test_models_argo.py`

## Feasibility

- The issue premise is confirmed by the code in src/devops_cli/models/argo.py: ArgoCDApp.from_api_item (line 40) reads spec.get('source', {}) then source.get('repoURL', ''), and ArgoResourceState.from_manifest (line 155) reads _section(spec, 'source').get('repoURL', ''). Neither reads spec.sources.
- The Argo CD Application spec defines spec.sources as a list of the same source objects, so spec.sources[0].repoURL is a valid fallback.
- First check: run uv run devops ci test tests/test_models_argo.py to confirm the new tests fail before the fix and pass after.
- Second check: run uv run devops argo cd apps list against a cluster with a multi-source Application and confirm the Repo column is populated.

## Existing Tool Considered

No external tool covers this need. It is a bug in the project's own model code in src/devops_cli/models/argo.py. The fix adds a fallback read of spec.sources[0].repoURL. The written cost is a few lines of code to build, keep and fix, well under one hour of elapsed time. No internal code is deleted.

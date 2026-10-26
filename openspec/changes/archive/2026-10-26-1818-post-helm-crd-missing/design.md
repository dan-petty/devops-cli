# Design

## Context

See `proposal.md` for motivation.
`_delete_post_helm_paths` deletes manifests with `kubectl delete -f <path> --ignore-not-found`.
When the cluster does not have the CRD installed, `kubectl delete` exits 1.
`_apply_post_helm_paths` delegates to `_apply_manifest_files`, which runs `kubectl apply -f` with `check=False` and hides missing CRD errors.

## Goals / Non-Goals

**Goals:**
- Query cluster API discovery using `kubectl api-resources` to verify resource kinds before operations.
- Skip post-Helm deletions safely when CRDs are not installed.
- Report skipped deletions with warning messages.
- Report post-Helm apply failures when CRDs are not installed during deployment.

**Non-Goals:**
- Automatically install missing CRDs during teardown.
- Change deletion behavior for non-post-Helm manifests.
- Alter Argo CD managed cluster flows.

## Decisions

### 1. Inspect manifests with PyYAML and query `kubectl api-resources`

We extract `(apiVersion, kind)` tuples from post-Helm manifest files using `yaml.safe_load_all`.
We query `kubectl api-resources` with `--api-group=<group>` for the manifest's group.
If the API group is not present or the kind is not listed, the helper returns false.

Rejected alternative: Catch `subprocess.CalledProcessError` from `kubectl delete`.
Evidence: Catching execution errors masks unexpected network or permission issues. Upstream guidelines prohibit swallowing errors when preconditions can be checked.

Rejected alternative: Query `kubectl get crd <crd-name>`.
Evidence: Mapping a resource kind to a CRD plural name requires custom heuristics. `kubectl api-resources` is the canonical discovery command and covers both CRDs and native kinds.

Rejected alternative: Set `check=False` on `_delete_post_helm_paths`.
Evidence: Setting `check=False` silences real deletion failures and leaves orphaned resources without warning.

### 2. Warn and skip on unserved kinds

If any kind in a manifest file is not served by the cluster:
- `_delete_post_helm_paths` prints a warning and skips `kubectl delete`.
- `_apply_post_helm_paths` prints a warning and skips `kubectl apply`.

## Risks / Trade-offs

[Additional discovery subprocess call] → Only runs for post-Helm manifests (at most two files per stack).
[Partial file support with multiple documents] → If any document kind in a manifest file is not served, the whole file is skipped to prevent partial failure.

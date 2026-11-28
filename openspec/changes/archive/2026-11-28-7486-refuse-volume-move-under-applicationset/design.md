# Design

## Decisions

- **Identify owning ApplicationSet via `metadata.ownerReferences`**: `_pause_order` already lists all Argo CD Applications in `DEFAULT_ARGOCD_NAMESPACE` and selects the `paused` tuple (Applications with `automated` sync enabled). For each Application in `paused`, inspect `metadata.ownerReferences` for entries with `kind == "ApplicationSet"`, `apiVersion == "argoproj.io/v1alpha1"` (built from `CONST_ARGO_API_GROUP` and `CONST_ARGO_API_VERSION`), and a non-empty `name`. Read each distinct ApplicationSet once via `kubectl get applicationset <name> -n <argocd_namespace> -o json`.
- **Check `spec.ignoreApplicationDifferences` with JSON Pointer segment matching**: An entry in `spec.ignoreApplicationDifferences` applies to an Application when the entry's `name` is empty or omitted (applies to all generated Applications) or equals the Application name. A pointer in `jsonPointers` covers the pause field when it starts with `/` and its slash-separated path segments form a non-empty prefix of `("spec", "syncPolicy", "automated", "enabled")` — accepting `/spec`, `/spec/syncPolicy`, `/spec/syncPolicy/automated`, and `/spec/syncPolicy/automated/enabled`, while rejecting sibling names such as `/spec/syncPolicy2` or unrelated paths such as `/spec/source/kustomize/images`.
- **Refuse before cluster mutations and update dry-run**: Append any refusal problem to `_pause_order`'s problem list so `plan_volume_move` collects all problems and raises `VolumeMoveRefusedError` without writing to the cluster. Add the conditional `kubectl get applicationset` read to `_dry_run_reads` after `kubectl get applications`.

## Rejected alternatives

- **Infer ApplicationSet ownership from Application name**: Rejected because Kubernetes and Argo CD record authoritative ownership in `metadata.ownerReferences` (`src/devops_cli/k8s/volume_move.py:566`), and an Application name does not prove which ApplicationSet owns it.
- **List all ApplicationSets and evaluate generator selectors**: Rejected because reproducing ApplicationSet generator matching adds complexity and can match an ApplicationSet that does not own the Application.
- **Match only exact `/spec/syncPolicy` or raw string prefix**: Rejected because exact matching would wrongly refuse valid narrower ignores such as `/spec/syncPolicy/automated/enabled`, whereas naive `str.startswith` would wrongly accept `/spec/syncPolicy2`.

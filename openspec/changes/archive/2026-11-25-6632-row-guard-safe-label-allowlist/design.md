# Design

## Decisions
- **Allowlist `_SAFE_ROW_LABELS` in `dispatch.py`**: Holds the complete set of non-workload/non-namespace labels kept by shipped `rows` facts plus quantile bucket labels (`alertname`, `cap`, `code_class`, `gpu`, `health_status`, `le`, `model`, `modelName`, `outcome`, `quantile`, `resource`, `result`, `row`, `rule_group`, `state`, `sync_status`). Shipped `rows` fact guard test proves completeness; any new non-namespaced label fails the test until explicitly reviewed and added.
- **Namespace check first, then allowlist**: Preserve `_NAMESPACE_LABELS` foreign checks first (`namespace`, `exported_namespace`, `dest_namespace`). When no foreign namespace exists and any namespace label holds a project namespace, any remaining labels pass. Otherwise skip `__name__` and reject the sorted first label not in `_SAFE_ROW_LABELS`.
- **Drop `_WORKLOAD_LABELS` from `dispatch.py`**: Default refusal makes the denylist redundant; `catalog.py` keeps its query-grouping `_WORKLOAD_LABELS` for load-time matcher enforcement.

## Rejected alternatives
- **Derive safe labels automatically from `catalog.yaml`**: Rejected because adding an unsafe unnamespaced label to `catalog.yaml` would widen the guard silently without review.
- **Keep both `_WORKLOAD_LABELS` and `_SAFE_ROW_LABELS`**: Rejected because two lists drift and split error reasons.

# Task 765: Handle Null Items Array in ArgoCD Applications Response

**Issue**: [#765](https://github.com/dan-petty/devops-cli/issues/765)
**Status**: Done
**Milestone**: `v0.2.24`
**Priority**: `priority/p2-medium`
**Scope**: `type/bug`, `scope/k8s`, `priority/p2-medium`

---

## 1. Description & Objectives

When querying ArgoCD for applications via `devops argo cd apps list`, an ArgoCD instance containing zero applications returns `{"metadata": {...}, "items": null}` due to Go protobuf JSON serialization semantics.

Previously, `_build_apps_table` performed:
```python
items = data.get("items", []) if isinstance(data, dict) else []
```
Because the `items` key is present with value `None`, Python dictionaries return `None` rather than the default `[]`. Subsequent iteration `for item in items:` raised:
```
TypeError: 'NoneType' object is not iterable
```

### Key Deliverables Completed:
- [x] **Safe Items Coercion in ArgoCD Table Formatter** (`src/devops_cli/commands/argo.py`):
  - Updated `items = (data.get("items") or []) if isinstance(data, dict) else []` to ensure `None` gracefully falls back to an empty list.
- [x] **Unit Test Verification** (`tests/test_argo.py`):
  - Added `test_argo_cd_apps_list_null_items` mocking `{"metadata": {}, "items": None}` and asserting exit code 0 with clean table output.
  - Asserted using structural tuple equality to ensure strict McCabe cyclomatic complexity $M \le 10$.

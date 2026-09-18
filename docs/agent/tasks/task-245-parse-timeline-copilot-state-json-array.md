# Task 245: Handle JSON Array Timeline Payload in PR Copilot State Parser

**Issue**: [#245](https://github.com/dan-petty/devops-cli/issues/245)
**PR**: [#246](https://github.com/dan-petty/devops-cli/pull/246)
**Status**: In Review
**Milestone**: `v0.2.20`
**Priority**: `priority/p1-high`
**Scope**: `scope/cli`, `scope/github`

---

## 1. Description & Objectives

When `devops pr monitor` or `devops pr wait` runs against a pull request, `_query_timeline_copilot_state` executes:
```bash
gh api --paginate repos/{owner}/{repo}/issues/{pr}/timeline --jq '.[] | select(.event | test("copilot|reviewed")) | ...'
```
When there are no matching timeline events, `run_gh` or `gh` returns a JSON array string `[]`. When events exist, it may return NDJSON (newline-delimited JSON objects) or a JSON array of objects.

In `_parse_timeline_copilot_state`:
```python
evt = json.loads(line_str)
evt_name = evt.get("event")
```
If `line_str` is a JSON array (such as `[]` or `[{...}]`), `json.loads` returns a `list`. Calling `evt.get("event")` raises:
`AttributeError: 'list' object has no attribute 'get'`
causing `devops pr monitor` to crash.

#### Key Deliverables:
1. **JSON Array & Dict Payload Safety ([`src/devops_cli/github/pr_monitor.py`](file:///workspaces/devops-cli/src/devops_cli/github/pr_monitor.py))**:
   - Normalize parsed payload in `_parse_timeline_copilot_state` to handle both lists and dictionaries.
   - Iterate through elements safely if `evt` is a list, extracting events and authors without throwing `AttributeError`.
2. **Submodule Unit Tests ([`tests/test_github_pr_monitor.py`](file:///workspaces/devops-cli/tests/test_github_pr_monitor.py))**:
   - Add unit tests verifying `_parse_timeline_copilot_state` handles:
     - Empty JSON array `[]`
     - Populated JSON array `[{"event": "copilot_work_started"}, ...]`
     - NDJSON lines `{"event": "copilot_work_started"}\n{"event": "reviewed"}`
     - Invalid JSON lines and mixed content.
3. **Quality & Architectural Invariant Gates**:
   - Strictly enforce cyclomatic complexity $\le 10$ and nesting depth $\le 5$.
   - 100% passing across all 10 CI quality gates (`uv run devops ci`).

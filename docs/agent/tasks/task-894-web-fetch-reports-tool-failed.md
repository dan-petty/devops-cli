# Task 894: web_fetch Reports Failed Fetch as Tool Failure, Not Page Text

**Issue**: [#894](https://github.com/dan-petty/devops-cli/issues/894)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: type/fix, scope/ai

---

## 1. Description & Objectives

The agent `web_fetch` tool previously caught all generic exceptions and returned an error string:
`f"Error fetching web page {url[:256]}: {str(exc)[:256]}"`
as normal page text (`content`).

This had significant negative consequences:
1. Downstream LLM agents and evaluation pipelines interpreted error strings as valid web page content rather than recognizing that the tool invocation had failed.
2. HTTP failures (e.g. 404 Not Found, 500 Server Error, connection drops, transport timeouts) were disguised as successful tool completions with status `"success"`.
3. Pre-flight SSRF validations and redirect vetoes (e.g. `SSRFBlockedError`, `ValueError` for blocked domains) were also caught and returned as page text rather than propagating as tool errors.

This deliverable:
- Modifies `web_fetch_tool` in `src/devops_cli/ai/common_tools.py` to catch `httpx2.HTTPError` specifically and raise `ToolFailed(f"Failed to fetch {url[:256]}: {str(exc)[:256]}") from exc`.
- Allows `SSRFBlockedError` and domain validation `ValueError` exceptions to propagate unmasked so the agent runner dispatches them with status `"error"`.
- Adds tests in `tests/test_common_tools.py` verifying that non-2xx status codes and connection failures raise `ToolFailed`, redirect violations raise `SSRFBlockedError` / `ValueError`, and the agent tool execution runner maps these exceptions to `"tool_failed"` and `"error"` respectively.

---

## 2. Acceptance Criteria

- [x] Non-2xx responses and HTTP transport errors raise `ToolFailed` and are never returned as page text.
- [x] SSRF blocks and blocked domain redirects propagate without being swallowed as page text.
- [x] Agent runner dispatches `ToolFailed` to `tool_failed` status and SSRF blocks to `error` status.
- [x] Unit tests cover non-2xx responses, transport connection failures, redirect violations, and runner status dispatching.
- [x] Changelog fragment `changelog.d/894.md` authored.
- [x] Gated CI quality checks pass in `uv run devops ci`.

---

## 3. Deliverables

- [x] `src/devops_cli/ai/common_tools.py`: Replace generic exception swallowing with `ToolFailed` on `httpx2.HTTPError`.
- [x] `tests/test_common_tools.py`: Unit tests for non-2xx `ToolFailed`, connection failure `ToolFailed`, and runner dispatching.
- [x] `changelog.d/894.md`: Changelog entry.
- [x] `docs/agent/tasks/task-894-web-fetch-reports-tool-failed.md`: Task documentation.

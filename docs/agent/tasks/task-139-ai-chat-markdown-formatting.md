# Task 139: Format AI Chat Responses as Rich Markdown When Syntax Detected

**Issue**: [#139](https://github.com/dan-petty/devops-cli/issues/139)
**PR**: TBD
**Status**: In Progress
**Milestone**: `v0.2.16`
**Priority**: `priority/p2-medium`
**Scope**: `scope/ai`

---

## 1. Description & Architectural Objectives

In `devops ai chat`, format AI assistant responses using Rich Markdown rendering (`print_markdown` / `rich.markdown.Markdown`) whenever markdown syntax (code blocks, headings, lists, tables, bold/italic formatting, links) is detected in the persona's response. When the response is plain text without markdown syntax, preserve clean informational text rendering without extraneous formatting artifacts.

### Key Acceptance Criteria
1. Implement `is_markdown_syntax(text: str) -> bool` to reliably detect markdown syntax elements (code fences, inline backticks, headings, bullet/numbered lists, blockquotes, tables, bold/italic, links).
2. Implement `render_chat_response(reply: str, *, console: Any = None) -> None` rendering markdown responses via Rich `Markdown` and plain text via standard console output.
3. Update `devops ai chat` in `src/devops_cli/commands/ai.py` to route replies through `render_chat_response`.
4. Export `is_markdown_syntax` and `render_chat_response` from `devops_cli.output`.
5. Author comprehensive unit tests in `tests/test_output.py` and `tests/test_ai_cmd.py` verifying markdown detection, rendering, and interaction turns.
6. Verify all 10 CI quality gates pass (`devops ci`).

---

## 2. Implementation Progress

- [x] Ground issue in GitHub tracking (#139) under milestone `v0.2.16`.
- [x] Create task tracking document `docs/agent/tasks/task-139-ai-chat-markdown-formatting.md`.
- [x] Author test-first unit tests for markdown syntax detection and chat response rendering in `tests/test_output.py`.
- [x] Implement `is_markdown_syntax` and `render_chat_response` in `src/devops_cli/output/console.py`.
- [x] Export `is_markdown_syntax` and `render_chat_response` in `src/devops_cli/output/__init__.py`.
- [x] Update `devops ai chat` in `src/devops_cli/commands/ai.py` to use `render_chat_response`.
- [x] Add integration unit test in `tests/test_ai_cmd.py`.
- [x] Verify unit tests, ruff, mypy, and full CI suite (`devops ci`).

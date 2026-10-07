# Task 896: web_fetch Renders Pages as Untrusted, Escaped Markdown Within a Budget

**Issue**: [#896](https://github.com/dan-petty/devops-cli/issues/896)
**Status**: Done
**Milestone**: v0.2.28
**Priority**: priority/p1-high
**Scope**: type/security, scope/ai

---

## 1. Description & Objectives

Previously, `_html_to_markdown` in `src/devops_cli/ai/common_tools.py` stripped only `<script>` and `<style>` tags via naive regular expressions and escaped no special characters. This allowed untrusted web pages to inject raw markdown headings (`# Injected Heading`), list items, or prompt instructions directly into the LLM context. Furthermore, chrome elements (`<header>`, `<nav>`, `<footer>`, `<aside>`) and dialog/modal popups (`<dialog>`, `[role=dialog]`) polluted the model context, and code fences inside `<pre>` blocks could break outer formatting if the snippet contained triple backticks.

This deliverable implements PR4 of the web fetch hardening sequence:
- Declares direct dependencies on `markdownify>=1.2` and `beautifulsoup4>=4.15.0` in `pyproject.toml`.
- Implements `render_untrusted_page(html, url, budget)` returning a structured `RenderedUntrustedPage`:
  - **Dynamic Code Fencing (`UntrustedMarkdownConverter.convert_pre`)**: Inspects enclosed backtick runs and generates code fences strictly longer than any internal backtick run to prevent fence smuggling.
  - **Chrome & Dialog Decomposition (`_clean_and_decompose_html`)**: Decomposes `<header>`, `<nav>`, `<footer>`, `<aside>`, `<dialog>`, and any element with `role="dialog"` (including `<main role="dialog">`), populating `removed_regions`.
  - **Provenance Isolation**: Decomposes any `<base>` tag so base href spoofing cannot tamper with provenance; derives the provenance line strictly from the response URL (`Provenance: {url}`).
  - **Blank-Line Budget Truncation (`_apply_blank_line_cut`)**: Truncates content exceeding the budget at the latest blank line (`\n\n`) and appends `DEFAULT_TRUNCATION_SUFFIX` (`\n...[truncated due to context budget]`), setting `truncated=True`.
  - **Prompt Boundary Tag Isolation**: Passes converted text through `sanitize_prompt_boundary_tags` and wraps the result in `<untrusted_web_page>`.
  - **Non-blocking Injection Scanning**: Scans raw HTML and converted markdown for prompt injection signatures via `PromptInjectionDefender().scan_text()`, flagging `injection_suspected=True` without aborting execution.
  - **Token Estimation**: Computes `token_estimate` over the wrapped markdown using `count_tokens()`.
- Replaces `_html_to_markdown` and deletes the `WebFetchLocalTool` fallback stub in `common_tools.py`.
- Integrates `render_untrusted_page` into `web_fetch_tool`.
- Adds unit tests in `tests/test_common_tools.py` verifying all security properties and edge cases.

---

## 2. Acceptance Criteria

- [x] Direct dependencies `markdownify>=1.2` and `beautifulsoup4>=4.15.0` declared in `pyproject.toml`.
- [x] `UntrustedMarkdownConverter.convert_pre` generates fences longer than any backtick run.
- [x] Chrome elements and `[role=dialog]` elements (including `<main role="dialog">`) are decomposed and recorded in `removed_regions`.
- [x] Provenance line is derived strictly from the response URL, never `<base>`.
- [x] Budget cut trims at blank lines and appends `DEFAULT_TRUNCATION_SUFFIX`.
- [x] Converted markdown is sanitized via `sanitize_prompt_boundary_tags` and wrapped in `<untrusted_web_page>`.
- [x] Prompt injection patterns flag `injection_suspected` without blocking.
- [x] `_html_to_markdown` and `WebFetchLocalTool` fallback stub removed.
- [x] Unit tests cover all behaviours and pass with `httpx2.MockTransport` without network access.
- [x] Changelog fragment `changelog.d/896.md` authored.
- [x] Gated CI quality checks pass in `uv run devops ci`.

---

## 3. Deliverables

- [x] `pyproject.toml` & `uv.lock`: Direct dependencies for `markdownify` and `beautifulsoup4`.
- [x] `src/devops_cli/config/constants.py`: `CONST_WEB_FETCH_CHROME_TAGS`.
- [x] `src/devops_cli/config/__init__.py`: Export `CONST_WEB_FETCH_CHROME_TAGS`.
- [x] `src/devops_cli/security/sanitizer.py`: Add `untrusted_web_page` to `_PROMPT_BOUNDARY_TAGS`.
- [x] `src/devops_cli/ai/common_tools.py`: Implement `UntrustedMarkdownConverter`, `RenderedUntrustedPage`, `render_untrusted_page`, and update `web_fetch_tool`.
- [x] `tests/test_common_tools.py`: Unit tests for `render_untrusted_page` and `web_fetch_tool`.
- [x] `changelog.d/896.md`: Changelog entry.
- [x] `docs/agent/tasks/task-896-web-fetch-untrusted-escaped-markdown.md`: Task documentation.

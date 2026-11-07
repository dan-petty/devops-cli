# Tasks

## 1. Add the command and its dry run

Kind: behavior

- [x] 1.1 In `tests/commands/test_ai_fetch_page.py`, add failing tests with the HTTP fake: the output holds the source URL and the text; a cut text shows `truncated`; a private host and a `file:` URL exit non-zero with the reason and send no request; an empty `crawl4ai.url` is named; HTTP 503 exits non-zero; `--dry-run` sends no request and prints the request with a token placeholder
  - Verification: `$ uv run devops ci test tests/commands/test_ai_fetch_page.py`
- [x] 1.2 Add the command `fetch-page` to `src/devops_cli/commands/ai.py`, its help and messages, the public functions `checked_page_url` and `crawl4ai_service` in `src/devops_cli/ai/page_text.py`, and `plan_ai_fetch_page` in `src/devops_cli/ai/ai_plans.py`
  - Verification: `$ uv run devops ci test tests/commands/test_ai_fetch_page.py tests/ai/test_page_text.py`

## 2. Expose the command as a read-only MCP tool

Kind: behavior

- [x] 2.1 In `tests/ai/mcp/test_ai_fetch_page_tool.py`, add failing tests: the tool `ai_fetch_page` exists, is read-only and is in the `ai` domain; its schema holds `url` and `dry_run` only; no job role holds it
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_ai_fetch_page_tool.py`
- [x] 2.2 Add the row `(("ai", "fetch-page"), 120.0, True, False)` to `CONST_MCP_EXPOSURE_TABLE`
  - Verification: `$ uv run devops ci test tests/ai/mcp`

## 3. Document the workstation setup

Kind: other

- [x] 3.1 Describe the setup in the help text of the command and of `devops mcp`, add the section to `k8s/README.md`, and regenerate the documents
  - Verification: `$ uv run devops docs generate --sync-readme`
  - Verification: `$ uv run devops docs generate --check`

## 4. Archive

Kind: other

- [x] 4.1 Archive the change
  - Verification: `uv run devops openspec archive 3892-fetch-page-command`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

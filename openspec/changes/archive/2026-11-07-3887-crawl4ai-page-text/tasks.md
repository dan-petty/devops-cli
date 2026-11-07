# Tasks

## 1. Fetch the text of a page through the Crawl4AI service

Kind: behavior

- [x] 1.1 In `tests/ai/test_page_text.py`, add failing tests with the HTTP fake: a good call sends the bearer header and the body; the source URL is the requested URL; the text is cut at the cap; a private, loopback, metadata or non-http page URL is refused before any request; a status of 401, 403, 429, 500 or 504 counts as itself and logs no token and no query; a redirect is not followed; no answer or no page text counts `error`; a reply over the byte cap is refused; an empty `crawl4ai.url` or token raises an error that names it. Add the reply fixture `tests/fixtures/crawl4ai/md_response.json`
  - Verification: `uv run devops ci test tests/ai/test_page_text.py`
- [x] 1.2 Add `src/devops_cli/ai/page_text.py`, the setting `crawl4ai.url`, the credential `crawl4ai.api_token`, the counter `devops_cli_crawl4ai_fetches_total`, the error `PageTextError` and the defaults and constants that they use
  - Verification: `uv run devops ci test tests/ai/test_page_text.py`

## 2. Document the setting, the credential, the counter and the error

Kind: other

- [x] 2.1 Name the cluster value `http://crawl4ai.devops.svc.cluster.local:11235` in `k8s/devops/configmap.example.yaml`, and regenerate the documents
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Archive

Kind: other

- [x] 3.1 Archive the change
  - Verification: `uv run devops openspec archive 3887-crawl4ai-page-text`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

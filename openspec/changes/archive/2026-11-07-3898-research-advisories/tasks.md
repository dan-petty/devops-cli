# Tasks

## 1. OSV client

Reads: `src/devops_cli/security/vulnerability_lookup.py`, `tests/security/test_vulnerability_lookup.py`. Changes: `src/devops_cli/security/vulnerability_lookup.py`, `src/devops_cli/exceptions/security.py`, `src/devops_cli/config/defaults.py`, `tests/security/test_vulnerability_lookup.py`.

- [x] 1.1 Add the tests of the record read, the byte cap, the redirects, the next page, the chunks and the client name
  - Verification: `uv run devops ci test tests/security/test_vulnerability_lookup.py`
- [x] 1.2 Add `get_vulnerability`, the stream read with the byte cap, the chunks of a batch, the next-page failure and the User-Agent
  - Verification: `uv run devops ci test tests/security/test_vulnerability_lookup.py tests/http/test_http_egress.py`

## 2. Advisories of the pins

Reads: `src/devops_cli/research/inventory.py`, `src/devops_cli/commands/research.py`. Changes: `src/devops_cli/research/advisories.py`, `src/devops_cli/research/models.py`, `src/devops_cli/commands/research.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/lang/en/`, `tests/research/test_advisories.py`, `tests/commands/test_research_advisories.py`, `tests/fixtures/research/advisories/`, `tests/ai/mcp/__snapshots__/`.

- [x] 2.1 Record the answers of api.osv.dev and the output of osv-scanner 2.6.0 for a lock with three packages, and add the tests of the findings, the reference, the plan of queries, the failures and the command
  - Verification: `uv run devops ci test tests/research/test_advisories.py tests/commands/test_research_advisories.py`
- [x] 2.2 Add the report model, `find_advisories`, `advisory_requests`, the command `devops research advisories` and its MCP tool
  - Verification: `uv run devops ci test tests/research tests/commands/test_research_advisories.py tests/ai/mcp/test_mcp_tool_listing.py`

## 3. Documentation

Reads: `README.md`. Changes: `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/research.md`, `docs/MCP_TOOLS.md`, `docs/ERRORS.md`.

- [x] 3.1 Regenerate the command pages, the error table and the MCP tool list
  - Verification: `uv run devops docs generate --check`

## Workflow follow-up

- Not in this change: the GitHub advisories source, the CISA KEV flag, the Qdrant server case and the components that OSV cannot match. Issue #3987 holds them. Issue #3988 holds the advisories that the command found in the requirement files of the tools lock.
- Pending a person: approve `api.github.com` (advisories API) and `www.cisa.gov` as egress destinations of the research agent.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

# Tasks

## 1. Shared public API helper

Reads: `src/devops_cli/security/vulnerability_lookup.py`, `tests/security/test_vulnerability_lookup.py`. Changes: `src/devops_cli/http/public_api.py`, `src/devops_cli/security/vulnerability_lookup.py`.

- [x] 1.1 Move the client builder and the bounded JSON read of the OSV client to `devops_cli.http.public_api`, and delete `_osv_json` and `_public_api_client`; the OSV tests stay unchanged
  - Verification: `uv run devops ci test tests/security/test_vulnerability_lookup.py tests/http/test_http_egress.py`

## 2. GitHub advisories, KEV and the match of versions

Reads: `src/devops_cli/http/public_api.py`, `src/devops_cli/research/advisories.py`. Changes: `src/devops_cli/research/github_advisories.py`, `src/devops_cli/research/kev.py`, `src/devops_cli/research/version_match.py`, `src/devops_cli/research/watch.py`, `src/devops_cli/config/defaults.py`, `.devops/research-watch.toml`, `tests/research/`, `tests/fixtures/research/advisories/github/`, `tests/fixtures/research/advisories/github_repo/`, `tests/http/test_http_egress.py`, `tests/security/test_vulnerability_lookup.py`.

- [x] 2.1 Record the answers of api.github.com and www.cisa.gov, and add the tests of the version match, the watch list and the byte cap, redirect, next page and token rules of the two clients
  - Verification: `uv run devops ci test tests/research/test_version_match.py tests/research/test_watch_list.py tests/research/test_github_advisories.py tests/research/test_kev.py`
- [x] 2.2 Add `GitHubAdvisoryClient`, `KevClient`, `pinned_version`, `in_range`, the watch list reader and the watch list file
  - Verification: `uv run devops ci test tests/research tests/http/test_http_egress.py tests/security/test_vulnerability_lookup.py`

## 3. The report and the command

Reads: `src/devops_cli/commands/research.py`. Changes: `src/devops_cli/research/advisories.py`, `src/devops_cli/research/models.py`, `src/devops_cli/commands/research.py`, `src/devops_cli/lang/en/`, `tests/research/test_advisories.py`, `tests/commands/test_research_advisories.py`.

- [x] 3.1 Add the tests of the Action finding, the Qdrant advisories, the exploited flag, the failed reads, the unreadable range, the unpinned count, the token and the dry run
  - Verification: `uv run devops ci test tests/research/test_advisories.py tests/commands/test_research_advisories.py`
- [x] 3.2 Plan the GitHub reads, match the versions, flag the CVEs of the KEV list, and print the Exploited column and the failures
  - Verification: `uv run devops ci test tests/research tests/commands/test_research_advisories.py tests/ai/mcp/test_mcp_tool_listing.py`

## 4. Documentation

Reads: `README.md`. Changes: `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/research.md`, `docs/MCP_TOOLS.md`, `openspec/specs/public-api-egress/spec.md`, `openspec/specs/research-advisories/spec.md`.

- [x] 4.1 Regenerate the command pages and the MCP tool list
  - Verification: `uv run devops docs generate --check`
- [x] 4.2 Record the egress approval and the two new clients in the spec `public-api-egress`
  - Verification: `uv run devops openspec check`

## Workflow follow-up

- Not in this change: a resolve of a pinned commit to its release. Issue #4012 holds it.
- Not in this change: a mapping for charts, providers and features whose versions are not versions of a repository. Nothing can match them without a source of such versions, so no issue holds it.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

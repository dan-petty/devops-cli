# Proposal

## Why

Issue #3892: an agent on a workstation (Claude Code, VS Code, Kilo) has no tool that reads a page through the cluster service. The client `fetch_page_text` (#3887) exists, and no command or tool uses it. The Crawl4AI MCP endpoint is not a fit: it serves SSE only, it has a wide tool surface (`execute_js`, `crawl`, `screenshot`, `pdf`), and it needs a bearer header, while SECURITY.md rule 12 says that no tool parameter takes a secret.

## What Changes

- New command `devops ai fetch-page <url>` in `src/devops_cli/commands/ai.py`. It calls `fetch_page_text` and prints a header (the source URL, the time of the fetch, and `truncated` when the text was cut), then the page text. The header comes first so that a cut of the output never hides it. A refused page URL, a failed fetch and an empty `crawl4ai.url` or token raise the errors of `fetch_page_text`, so the command exits non-zero with the reason.
- The command has the option `--dry-run` and no other option. It has no option for the service URL, the token, the text cap or a file path: the service comes from the setting `crawl4ai.url` and the token from the credential store. `--dry-run` makes no request. It checks the page URL and the setting, then prints the request that the real run would send, with the token as the placeholder `<crawl4ai.api_token>`.
- `fetch_page_text` gives its two local checks to the dry run: `checked_page_url` and `crawl4ai_service` are public functions of `src/devops_cli/ai/page_text.py`, and `plan_ai_fetch_page` in `src/devops_cli/ai/ai_plans.py` uses them.
- New row `(("ai", "fetch-page"), 120.0, True, False)` in `CONST_MCP_EXPOSURE_TABLE`. The generator then publishes the tool `ai_fetch_page` in the `ai` domain, read-only. Its schema holds `url` and `dry_run`.
- The tool is not in `_JOB_ROLE_TOOLS`. It reads pages from the web, which is new egress, and a person must approve that first (#3243). Only the `ops` role holds it.
- Help text, `docs/commands/ai.md`, `docs/MCP_TOOLS.md` and `docs/commands/mcp.md` (generated) and `k8s/README.md` explain the workstation setup: `kubectl port-forward -n devops svc/crawl4ai 11235:11235`, `crawl4ai.url` set to `http://127.0.0.1:11235`, and the token stored with `devops config set crawl4ai.api_token`.
- No change to `.mcp.json`, `.vscode/mcp.json` or `kilo.jsonc`: the tool arrives through the existing `devops-cli` server.
- The change adds a command and a tool that a consumer observes, so it carries a spec delta that creates the capability `ai-fetch-page`.
- This change fits one pull request. It builds on origin/main only, and it does not need the work of #3890.

## Capabilities

### New Capabilities

- `ai-fetch-page`: the command `devops ai fetch-page` and the MCP tool `ai_fetch_page` that read the text of one page through the Crawl4AI service, with a schema that takes no secret, no service address and no path.

## Impact

- `src/devops_cli/commands/ai.py`, `src/devops_cli/ai/page_text.py`, `src/devops_cli/ai/ai_plans.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`.
- `tests/commands/test_ai_fetch_page.py` (new), `tests/ai/mcp/test_ai_fetch_page_tool.py` (new), `tests/ai/test_page_text.py`.
- `docs/commands/ai.md`, `docs/commands/mcp.md`, `docs/MCP_TOOLS.md`, `k8s/README.md`.

## Feasibility

- The client `fetch_page_text` is on origin/main (`src/devops_cli/ai/page_text.py`, #3887). It raises `InvalidURLError`, `SSRFBlockedError`, `ConfigurationError` and `PageTextError`, which `devops_cli.core.cli` reports as the error of a command with the exit code of the error.
- `src/devops_cli/ai/mcp/generator.py` builds a tool from each row of `CONST_MCP_EXPOSURE_TABLE` and publishes one schema property for each Click parameter. A command with the one argument `url` and the flag `--dry-run` therefore publishes exactly those two properties (checked with `tests/ai/mcp/test_mcp_exposure_table.py`).
- `tests/ai/mcp/test_mcp_tool_secrets.py` fails for a text parameter with a secret word in its name. `url` is not such a name.
- `http_client(level=EgressLevel.PRIVATE)` admits `127.0.0.1`, so a port-forward address works as `crawl4ai.url` (`_LEVEL_ADMITS` in `src/devops_cli/http/egress.py`).
- No Crawl4AI service runs yet (#3884 plans it), so the command is tested against the HTTP fake and the reply shape that #3887 fixed. A live check is #3894.

## Existing Tool Considered

- The MCP generator from Typer commands (`ai/mcp/generator.py`), the existing `devops-cli` MCP server, and the client `fetch_page_text`. The change adds one command and one table row, and no new mechanism.
- Rejected: a second MCP server entry for Crawl4AI. The token would sit in a client config file, the endpoint serves SSE only, and its tool surface includes `execute_js`, `crawl`, `screenshot` and `pdf`. Rejected: Kindly (see the decision text of the issue).
- The change deletes no internal code.

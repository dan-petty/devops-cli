# Proposal

## Why

Issue #3898: `devops ci audit` checks only `uv.lock` and the Node lock files. The hashed requirement files of the tools lock (Semgrep and Bandit) are not checked, and GitHub gives no alert because Dependabot alerts are off. A run on 2026-11-07 shows the gap: the pins of `semgrep.txt` hold seven advisories (`certifi`, `mcp`, `opentelemetry-api`) that no check reports. This change is the second slice of the research agent. It adds `devops research advisories`, which takes the pins of `devops research inventory` and returns the advisories that affect them, with no model.

## What Changes

- New command `devops research advisories`. It reads the inventory of the repository, asks OSV about the Python and Node packages that pin an exact version, and prints one finding for each advisory that affects a pin: component, locations, advisory id, aliases, severity, affected range, fixed version and summary. `--json` and `--format yaml` print the findings, the lookups that failed and a summary. The summary counts the packages asked about, the pins without an exact version, and the components that OSV cannot match, by ecosystem.
- A lookup that gets no answer is in the report and the command exits with code 1 after it prints. A component whose lookup failed is never shown as clean.
- The command has the `request-plan` dry-run class: `--dry-run` lists the OSV requests and sends none. It has a read-only MCP tool with no argument.
- `OSVClient` gets `get_vulnerability`, which reads one record (`GET /v1/vulns/{id}`) for the ranges and the fixed versions that a batch query does not give.
- `OSVClient` reads each answer as a stream and refuses an answer over `DEFAULT_OSV_MAX_RESPONSE_BYTES` (4 MiB). It sends a batch of at most `DEFAULT_OSV_BATCH_MAX_QUERIES` (1000) queries, as the API takes, and one chunk that fails does not fail the others. A batch answer that has more pages is a failed lookup, because the client reads the first page only. The three public API clients (OSV, Shodan InternetDB and Cloudflare Radar) name themselves `devops-cli/<version>`.
- Observable behavior changes (a command, an MCP tool, an exit code, client limits), so the change carries spec deltas: the new capability `research-advisories`, and added requirements of `public-api-egress`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `research-advisories`: The advisories that `devops research advisories` finds for the pins of a repository.

### Modified Capabilities

None. `public-api-egress` gets added requirements only.

## Impact

- Code: `src/devops_cli/research/advisories.py`, `src/devops_cli/research/models.py`, `src/devops_cli/commands/research.py`, `src/devops_cli/security/vulnerability_lookup.py`, `src/devops_cli/exceptions/security.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/constants.py` (MCP exposure table), `src/devops_cli/ai/mcp/generator.py`, `src/devops_cli/lang/en/`.
- Tests: `tests/research/test_advisories.py`, `tests/commands/test_research_advisories.py`, `tests/security/test_vulnerability_lookup.py`, `tests/fixtures/research/advisories/` (the answers of api.osv.dev and the output of osv-scanner 2.6.0, both recorded on 2026-11-07).
- Documents: `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/research.md`, `docs/MCP_TOOLS.md` and `docs/ERRORS.md`, all generated.
- No new dependency, no secret, no new instrument, and no new host: the only host is `api.osv.dev`, which `public-api-egress` already names.

## Not in this change

The issue lists three sources: OSV, `GET /advisories` of GitHub and the CISA KEV list. This change builds the first. The other two send requests to hosts that no document of the repository approves as egress destinations (`api.github.com` for the advisories API, and `www.cisa.gov`), and an approval is a decision of a person. Issue #3987 holds them, with these criteria of #3898: the GHSA source and the Qdrant server advisories (GHSA-3gph-6c29-p29v and GHSA-frc7-44gm-99qq), the `exploited` flag from the KEV list, the live call of `GET /advisories` with and without a token and the rate limit seen, and the findings for the components that OSV cannot match today: GitHub Actions, container images, charts and release binaries. OSV does not match the versions of GitHub Actions, so those need a matcher for versions of Actions on the OSV or GHSA ranges, and a mapping from an image, chart or binary to a package name (`.devops/research-watch.toml`).

The run on the real tree also found advisories in the hashed requirement files of the tools lock, which `devops ci audit` does not read. Issue #3988 holds that fix and its check.

## Feasibility

- Checked on 2026-11-07 against api.osv.dev with the project's client and with plain requests. `POST /v1/querybatch` with an exact version matches that version to the affected ranges: `idna` 3.6, `pyyaml` 5.3 and `jinja2` 2.4.1 give advisories, and `markupsafe` 2.1.5 and `jinja2` 3.1.6 give none. A batch answer holds the advisory ids only, with no severity and no range, so each id needs `GET /v1/vulns/{id}`.
- The reference agrees. The findings for the three packages of the fixture `uv.lock` are the eight ids that osv-scanner 2.6.0 reports for the same lock (zero difference). On the real tree, the findings for `src/devops_cli/tools_lock/semgrep.txt` are the six ids that osv-scanner 2.6.0 reports for the same file (`requirements.txt:` format).
- OSV does not match versions of GitHub Actions. A query for `tj-actions/changed-files` at `v45.0.0` and at `45.0.0` returned no result, and a query with no version returned both of its advisories, one of which says the versions before 46.0.1 are affected. The command therefore does not ask about Actions, and counts them as not covered.
- The key of a tool in the tools lock is not always the name of its package: the key `openspec` is `@fission-ai/openspec` on npm, and `openspec` on npm is another package. The command asks about the packages that the Python and Node lists hold, and counts the tool entries.
- The range type `GIT` of a record holds commit hashes. The command reads the ranges of the types `ECOSYSTEM` and `SEMVER` only.
- Redirects: the client of `OSVClient` is built by `http_client` with `follow_redirects` off (the httpx2 default), so a redirect is a status that is not 200 and the client sends no request to its target. The tests hold this.
- OSV states no limit on the API, and a run on this repository takes 340 package versions in one batch and 9 record reads, about 4 seconds.

## Existing Tool Considered

OSV (`api.osv.dev`) through `OSVClient`, which the project already uses, covers the need for the registry ecosystems. osv-scanner 2.6.0 is the reference of the tests and is not called by the command: `devops ci audit` runs it for lock files, and it reads no inventory of Actions, images and charts. GitHub's `GET /advisories`, CISA KEV, deps.dev and Trivy are not used here (see "Not in this change"). Version matching is not written here: OSV does it on the server with the exact version, so the change adds no matcher and no new dependency. The new code is the plan of queries, the report model and the command (about 300 lines with the client changes); it deletes no internal code.

# Proposal

## Why

Issue #3987: `devops research advisories` (#3898) asks OSV about the 373 Python and Node packages of the inventory and counts the other 181 of 558 components as not covered: 80 GitHub Actions, 47 images, 18 charts, 20 release binaries, 9 Terraform providers and 7 devcontainer features. OSV does not match versions of Actions, and it has no ecosystem for images, charts and binaries. The Qdrant server advisories GHSA-3gph-6c29-p29v and GHSA-frc7-44gm-99qq, which the Qdrant repository published, are in no OSV record. The report also does not say which finding is exploited. The owner approved the egress to `api.github.com` and `www.cisa.gov` on 2026-11-07, which was the open block of this item.

## What Changes

- `devops research advisories` reads GitHub advisories for two groups of components. For each GitHub Action with an exact release it reads the reviewed advisories that name the package (`GET /advisories?ecosystem=actions&affects=<names>`). For each image, chart or release binary that `.devops/research-watch.toml` maps to a repository it reads the advisories that the repository published (`GET /repos/{owner}/{repo}/security-advisories`). GitHub does not match versions, so the command matches the pinned version to the range of each advisory with `packaging`, including the ranges that `||` joins.
- A new file `.devops/research-watch.toml` maps a component (ecosystem and name) to its repository. It names the Qdrant chart, seven images and 17 of the 20 release binaries of the tools lock; the file says why it leaves out the other three. An entry may name the `package` that the repository gives to the component in its advisories, because a repository lists one vulnerability for each module or major version, and the range of another major version is no range of the pin. A test holds each binary entry to its `source` in `tools.lock`.
- The command reads the CISA KEV list (`www.cisa.gov`) once, when a finding names a CVE. A finding whose CVE is in the list has `exploited: true`. The table has an `Exploited` column, and the summary counts the exploited findings. A KEV list that cannot be read is `kev_failure` in the report, and the command exits with code 1 after it prints.
- A pin that names no one release (`v7`, a commit, a tag with a variant such as `-alpine`) is counted in `unpinned` and is not sent. This covers 47 of the 80 Actions of this repository, which name a major tag after the commit.
- Each finding has a `source` (`OSV` or `GitHub`). `--dry-run` lists the GitHub and KEV requests.
- Two new clients, `GitHubAdvisoryClient` and `KevClient`, and one shared helper, `devops_cli.http.public_api`: the client of a fixed public API and a bounded JSON read. `OSVClient` uses the helper too, so the three clients share one byte cap, redirect and name rule; this deletes the private `_osv_json` and `_public_api_client`.
- Observable behavior changes (a command output, an exit code, two new hosts), so the change carries spec deltas for `research-advisories` and `public-api-egress`. The egress approval is recorded in `public-api-egress`.
- No new instrument: the lookups use `devops_cli_vulnerability_lookups_total` with the source `github`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `research-advisories`: GitHub as a second source, the KEV flag, the watch list and the match of versions.
- `public-api-egress`: the two new hosts, with the approval, and the two new clients.

## Impact

- Code: `src/devops_cli/research/advisories.py`, `github_advisories.py`, `kev.py`, `version_match.py`, `watch.py`, `models.py`, `src/devops_cli/http/public_api.py`, `src/devops_cli/security/vulnerability_lookup.py`, `src/devops_cli/commands/research.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/lang/en/`.
- Tests: `tests/research/` (clients, match, watch list, advisories), `tests/commands/test_research_advisories.py`, `tests/http/test_http_egress.py`, `tests/security/test_vulnerability_lookup.py`, and the recordings of 2026-11-07 in `tests/fixtures/research/advisories/github/` and `github_repo/`.
- Documents: `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/research.md`, `docs/MCP_TOOLS.md` (generated).
- Data: `.devops/research-watch.toml`.
- No new dependency (`packaging`, `pydantic` and `httpx2` are in use) and no secret. The GitHub token is optional and goes to `api.github.com` only.

## Not in this change

- A mapping for Helm charts whose version has its own numbering (for example `argo-cd` 10.9.6), Terraform providers and devcontainer features: their versions are no versions of an upstream repository, so the watch list does not map them and the summary keeps counting them as not covered.
- A major tag such as `v7`: the command cannot tell which release the commit is. Resolving the commit to its release is a separate read of the tags of each Action's repository. Issue #4012 holds it.

## Feasibility

Checked on 2026-11-07 against the real systems.

- `GET https://api.github.com/advisories?ecosystem=actions&affects=tj-actions/changed-files&per_page=100`, with no token, answered 200 with two advisories: GHSA-mrrh-fwg8-r2c3 (CVE-2025-30066, `<= 45.0.7`, fixed in 46.0.1) and GHSA-mcph-m25j-8j63 (`< 41`). It answered with the headers `x-ratelimit-limit: 60`, `x-ratelimit-remaining: 59` and `x-ratelimit-resource: core`. The same list with the token of `gh` answered 200 with the same advisories and the limit 5000. `affects` takes up to 1000 packages, so one request covers every Action of the repository.
- GHSA-3gph-6c29-p29v and GHSA-frc7-44gm-99qq are not in `GET /advisories`: `GET /advisories/{ghsa_id}` answered 404 for both. The Qdrant repository published them: `GET /repos/qdrant/qdrant/security-advisories` lists them, with the package ecosystem `docker image / binary release`, the ranges `>= 1.18.0, < 1.19.2` and `< 1.20.0`, and the fixes 1.19.2 and 1.20.0. The Qdrant chart 1.19.1 of this repository is in both ranges. The issue named `GET /advisories` as the source; the repository endpoint is on the same host and in the same API family, and it is the one that has these records.
- `https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json` answered 200 with 1,832,349 bytes and 1,769 entries (catalog 2026.11.06) and no redirect. It lists CVE-2025-30066.
- The version ranges of GitHub advisories (`<= 45.0.7`, `< 41`, `>= 1.18.0, < 1.19.2`, `= 1.2.3`) are read by `packaging.specifiers.SpecifierSet` after `=` becomes `==`; a test holds twelve cases and the cases that must fail.
- Redirects: the helper builds the client with `http_client`, which follows no redirect unless a pooled client is asked to. A test for each client holds the redirect to another host, to a private address and to a metadata address.

## Existing Tool Considered

The GitHub REST API for advisories and the CISA KEV JSON file, through `httpx2` and the egress-checked client factory that the OSV client already uses, cover the need. osv-scanner 2.6.0 is reference only: it cannot match Actions, images or the Qdrant advisories. `packaging` compares the versions; no comparison is written here. The new code is the two clients (about 250 lines), the plan and the matching in `advisories.py` (about 150 lines) and the watch list reader (about 60 lines); the shared helper replaces about 40 lines of the OSV client. The change deletes `_osv_json` and `_public_api_client` of `vulnerability_lookup.py`.

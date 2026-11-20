# Proposal: #6405

## Why

Issue #6405: six image scan blocks in `ci.yml` and `release.yml` hold the same Trivy step. Each block sets up the uv toolchain and runs `devops install-tools --tool trivy` (25-28 s for each job), passes `skip-setup-trivy` and a `version:` input that has no effect, and writes a table only, with no SARIF. Three ignore files (`.trivyignore`, `.trivyignore-mcp-server`, `.trivyignore-tofu`) hold entries with no path scope, so an entry for one tool hides the same ID in each binary of the image. The MCP scan hid the kubectl findings CVE-2026-78669 and CVE-2026-78661 through the OpenTofu entries of `.trivyignore-tofu`.

## What Changes

- Add the composite action `.github/actions/image-scan`. It runs Trivy from `ghcr.io/aquasecurity/trivy`, pinned by tag and digest, as a `docker://` step: `--scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code <input> --ignorefile <input> --format sarif`. A second `docker://` step prints the same findings as a table from the cache of the scan, so the job log names each finding. `github/codeql-action/upload-sarif` uploads the SARIF under the category of the caller, also after a failed scan. The inputs are `image-ref`, `category`, `exit-code` (default 1) and `ignore-file` (default `.trivyignore.yaml`), so #6406, #6407, #1858 and #4361 can call it for other images.
- The six image jobs call the action with exit code 1 and the categories `trivy-image-service`, `trivy-image-runner` and `trivy-image-mcp-server`, and each job gets `security-events: write`. The calling step sets `timeout-minutes: 4`, because a step of a composite action has no timeout. The steps 'Set up uv toolchain' and 'Install Trivy', `skip-setup-trivy` and the `version:` inputs go.
- `third-party-image-scan.yml` calls the action with exit code 0 and category `trivy-image-crawl4ai`, and runs also when the action changes.
- `.trivyignore.yaml` holds each image finding under `vulnerabilities:`: one entry for each finding and binary, with `id`, `paths` (the Trivy target), `purls`, a `statement` that names the tracking issue, and `expired_at`. The three legacy files go, and `.trivyignore.yaml` and the action folder take their place in the 3 `IMAGE_CONTENT_PATHS` lists.
- The entry of CVE-2026-56851 in kubectl expired on 2026-11-20, so the MCP Server Image scan failed on `main`. The change renews it to 2026-11-22, the limit of 14 days from 2026-11-08, by the renewal rule of SECURITY.md (#6084). The other entries keep their dates.
- SECURITY.md, `docs/ROUTINE_TASKS.md`, `docs/CLUSTER.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/SDLC.md`, the `Dockerfile` comment, the `tools.lock` comment, `.github/renovate/base.json` and `pyproject.toml` stop to name the legacy files and trivy-action. `.github/renovate.json` loses the coupled `trivy` group: no test compares the pins now, and the built-in github-actions manager moves the tag and digest of the `docker://` image.
- Tests: `tests/support/trivyignore.py`, its unit tests, the stale-entry test, the release-equals-CI parity test and the trivy-action input assertions go (owner decision of 2026-11-19, rule of 2026-11-16: no test of a config value). The permission expectations get `security-events: write`, and `config_reads.toml` falls to the counts that the `test-tree` row measures.
- The specs `mcp-server-image`, `roadmap-implement-runner`, `crawl4ai-service` and `release-concurrency-and-renovate` name the legacy files or trivy-action, so the delta changes those requirements. The new capability `ci-image-scan` holds the action, its callers and the scoped entries.

The Trivy entry of `tools.lock` and the `trivy config` install of the static job stay for #4361 and #4363.

The change fits one pull request.

## Capabilities

### New Capabilities

- `ci-image-scan`: the image scan action, the jobs that call it and the scoped image entries of `.trivyignore.yaml`.

### Modified Capabilities

- `mcp-server-image`: the release scan uses the action of the pull request check; the requirements of the MCP ignore file go.
- `roadmap-implement-runner`: an image finding with no fix gets a scoped entry of `.trivyignore.yaml`.
- `crawl4ai-service`: the third-party scan uses the action.
- `release-concurrency-and-renovate`: the example of a version input is setup-uv.

## Impact

- `.github/actions/image-scan/action.yml` (new), `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/third-party-image-scan.yml`.
- `.trivyignore.yaml`; `.trivyignore`, `.trivyignore-mcp-server` and `.trivyignore-tofu` deleted.
- Code scanning gets one analysis category for each image. The image jobs need no uv toolchain.
- No command, option or message of `devops` changes.

## Feasibility

Read on 2026-11-20 against `origin/main` at `58e7b0dee`, with Docker 29.9.3 and Trivy 0.76.2.

- The GitHub metadata syntax for composite actions lists `docker://` references as examples of `runs.steps[*].uses`, and lists no `timeout-minutes` key for a composite step (https://docs.github.com/en/actions/reference/workflows-and-actions/metadata-syntax). The pull request runs the action in four jobs: the three image jobs of `ci.yml` and the third-party scan.
- `docker buildx imagetools inspect ghcr.io/aquasecurity/trivy:0.76.2` gives the index digest `sha256:8f6bb947dbc528902e11f2f5be52f7b519f6a39d5d148f41166f2040499768fb`. Its user is root and its entry point is `trivy`.
- `trivy image --ignorefile /dev/null` on the release images `v0.182.0` of service, runner and mcp-server gives 0, 11 and 15 HIGH or CRITICAL findings with a fix, each with its Target and purl. With the three legacy files on 2026-11-20, the MCP server image fails on CVE-2026-56851 in `opt/devops-tools/tools/kubectl/1.37.2/kubectl`: its entry has `exp:2026-11-20`.
- The two steps of the action, started with `docker run` as the runner starts a `docker://` step (the workspace as working directory, the Docker socket mounted), exit 0 on the three images with the new `.trivyignore.yaml`. The scan takes 54 s to 62 s with a new database; the table pass takes 1 s to 2 s.
- `--show-suppressed` on the MCP server image lists the 15 suppressed findings, each with only the binary of its entry. With the four kubectl `paths` changed to `1.37.1`, the scan exits 1 and reports the four kubectl findings again.
- `go.mod` of kubectl v1.37.2 and of branch `release-1.37` holds `golang.org/x/text v0.40.0` and `golang.org/x/net v0.57.0`. v1.37.2 (2026-10-28) is the newest stable release; v1.38.0-beta.0 is a pre-release.
- Pull time of the Trivy image on this host: 5 s.

## Existing Tool Considered

Trivy's official image `ghcr.io/aquasecurity/trivy` scans the images and writes SARIF and tables, and `github/codeql-action/upload-sarif` uploads the SARIF; Renovate's built-in github-actions manager moves both pins. The action only connects these tools and builds no scanner code. The change deletes `tests/support/trivyignore.py` and its tests, the six 'Set up uv toolchain' and 'Install Trivy' steps of the image jobs, and the `aquasecurity/trivy-action` steps.

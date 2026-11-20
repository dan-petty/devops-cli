# Tasks

## 1. One image scan action

Kind: other. Reads: `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/third-party-image-scan.yml`. Changes: `.github/actions/image-scan/action.yml`, the three workflows, `tests/invariants/test_mcp_server_image.py`, `tests/invariants/test_runner_image.py`, `tests/commands/test_ci.py`.

- [x] 1.1 Add the composite action `.github/actions/image-scan` with the inputs `image-ref`, `category`, `exit-code` and `ignore-file`: a `docker://` Trivy scan that writes SARIF, a table pass from its cache, and `upload-sarif` under the category
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
- [x] 1.2 Call the action from the six image jobs of `ci.yml` and `release.yml` with a step timeout of 4 minutes, grant `security-events: write`, and delete the steps 'Set up uv toolchain' and 'Install Trivy' and the trivy-action inputs. Delete the trivy-action input assertions, the release-equals-CI parity test and the three image-job 'Install Trivy' allowlist entries, and add `security-events: write` to the permission expectations
  - Verification: `$ uv run devops ci test tests/invariants/test_mcp_server_image.py tests/invariants/test_runner_image.py tests/commands/test_ci.py`
- [x] 1.3 Call the action from `third-party-image-scan.yml` with exit code 0 and category `trivy-image-crawl4ai`, and run the workflow when the action changes
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`

## 2. Scoped image ignore entries

Kind: data. Reads: `.trivyignore`, `.trivyignore-mcp-server`, `.trivyignore-tofu`, SECURITY.md. Changes: `.trivyignore.yaml`, the three legacy files, `.github/workflows/ci.yml`, `pyproject.toml`, `tests/support/trivyignore.py`, `tests/invariants/test_service_image.py`, `tests/invariants/test_mcp_server_image.py`, `tests/gate/tree_checks/config_reads.toml`, `tests/gate/tree_checks/config_values.py`.

- [x] 2.1 Move each image entry into `vulnerabilities:` of `.trivyignore.yaml`, one for each finding and binary, with `id`, `paths`, `purls`, `statement` and `expired_at`. Renew the kubectl CVE-2026-56851 entry to 2026-11-22 with the proof of SECURITY.md
  - Verification: `$ git ls-files .trivyignore .trivyignore-mcp-server .trivyignore-tofu`
- [x] 2.2 Delete the three legacy files, `tests/support/trivyignore.py`, its unit tests, the stale-entry test and the `.trivyignore-mcp-server` read of the kubectl and helm pin test. Name `.trivyignore.yaml` and the action folder in the 3 `IMAGE_CONTENT_PATHS` lists, remove `.trivyignore` from `also_copy`, and lower the counts of `config_reads.toml`
  - Verification: `$ uv run devops ci --check --only test-tree`

## 3. Renovate and documents

Kind: documents. Reads: `.github/renovate.json`, `.github/renovate/base.json`. Changes: `.github/renovate.json`, `.github/renovate/base.json`, `src/devops_cli/tools_lock/tools.lock`, `Dockerfile`, SECURITY.md, `docs/ROUTINE_TASKS.md`, `docs/CLUSTER.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/SDLC.md`.

- [x] 3.1 Remove the coupled `trivy` group of `.github/renovate.json`, name only setup-uv as the example of a version input in `.github/renovate/base.json`, and remove the trivy-action sentence of the `tools.lock` header
  - Verification: `$ uv run devops ci test tests/core/test_renovate_config.py`
- [x] 3.2 Name `.trivyignore.yaml` and the image scan action in SECURITY.md, `docs/ROUTINE_TASKS.md`, `docs/CLUSTER.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/SDLC.md` and the `Dockerfile` comment
  - Verification: `$ uv run devops ci --check --only docs`

## Workflow follow-up

- Pending a person: after the merge, run `uv run devops gh api 'repos/dan-petty/devops-cli/code-scanning/analyses?per_page=100' --jq '[.[].category] | unique'` and see `trivy-image-service`, `trivy-image-runner` and `trivy-image-mcp-server` in the list.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

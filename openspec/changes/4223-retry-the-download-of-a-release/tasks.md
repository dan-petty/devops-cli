# Tasks

## 1. Installer retries and names a body that is not the archive

Kind: behavior

- [ ] 1.1 In `tests/commands/test_install_tools.py`, write the cases for two 504 answers then the archive, a lost connection then the archive, an outage of one minute, a 504 that never ends, a 404, an HTML body with status 200 for each archive format, and a real archive with other bytes
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main`
- [ ] 1.2 In `src/devops_cli/commands/install_tools.py`, pass `retries=8` to `http_client` in `_download_client`. Add the check that refuses a body without the magic bytes of its format with `ToolDownloadError` before `_verify_sha256`
  - Verification: `$ uv run devops ci test tests/commands/test_install_tools.py`

## 2. The Dockerfile fetches gh with a retry

Kind: manifests

- [ ] 2.1 In `tests/ci/test_release_download_retries.py`, write the guard over the `Dockerfile`, the workflows, the composite actions and the installer
  - Verification: `$ uv run devops ci test tests/ci/test_release_download_retries.py`
- [ ] 2.2 In `Dockerfile`, replace the two `ADD --checksum` steps and the `RUN tar` step with one `RUN` step of the builder stage that fetches the tarball for `TARGETARCH` with `curl --retry`, checks its pinned SHA-256 with `sha256sum -c`, and installs `gh`
  - Verification: `! git grep -nE "ADD --checksum" -- Dockerfile`
- [ ] 2.3 In `tests/invariants/test_service_image.py`, keep the pin tests true for the new step
  - Verification: `$ uv run devops ci test tests/invariants/test_service_image.py tests/roadmap/test_roadmap_runner_tools.py`

## 3. Documents

Kind: documents

- [ ] 3.1 Fix each document that names the `ADD --checksum` step of the `Dockerfile` or says that `devops install-tools` makes one request
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- The retry of the Trivy download in the image scan steps: #4229.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

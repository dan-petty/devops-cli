# Proposal

## Why

A GitHub outage with HTTP 504 answers failed the checks of two pull requests three or four times in a row (#4223). Each rerun costs about 30 minutes, and a check that averages more than 5 minutes is a P0 bug. Three downloads of a release archive have no retry:

- `devops install-tools` fetches a locked build with one request. `_download` in `src/devops_cli/commands/install_tools.py` calls `_download_client()` and `get` once. `http_client` is called with no `retries=`.
- The `Dockerfile` fetches the `gh` tarballs with `ADD --checksum=sha256:<hash> <url>`. BuildKit `ADD` has no retry option. A 504 page then fails the `--checksum` check, so the error names a checksum failure while the pinned checksum is right.
- A 200 answer with an HTML error page reaches `_verify_sha256` and fails as a checksum mismatch. The error does not name the URL or say that the body is not the archive.

## What Changes

- `_download_client` in `src/devops_cli/commands/install_tools.py` passes `retries=` to `http_client`. The count covers an outage of about two minutes. A 4xx answer other than 429 is not retried.
- `install_binary` refuses a body that is not the archive before it checks the SHA-256. For the formats `gzip`, `tar.gz` and `zip`, a body without the magic bytes of the format raises `ToolDownloadError`. Its reason names the format, says that the body is not that archive, and gives the HTTP status. The `binary` format has no magic bytes and keeps the checksum check alone. The SHA-256 check stays unchanged.
- The `Dockerfile` has no `ADD` of a URL. A `RUN` step of the builder stage fetches the `gh` tarball with `curl --retry`, checks its pinned SHA-256 with `sha256sum -c`, and installs `gh`. The pinned checksums and the pinned release stay.
- `tests/ci/test_release_download_retries.py` fails for a remote `ADD`, for a `curl` or `wget` step with no retry option in the `Dockerfile`, the workflows and the composite actions, for a release URL in the `Dockerfile` with no checksum check, and for an installer client with no `retries=`.
- The change adds a spec because `devops install-tools` shows a new behavior to its caller: it retries, and it names a body that is not the archive. It fits one pull request.
- Work the change does not do: the image scan steps with `aquasecurity/trivy-action` keep the download of the action (see Feasibility). #4229 holds that work.

## Capabilities

### New Capabilities

- `release-download-retries`: A download of a release archive retries on a 5xx answer and on a connect failure, and a body that is not the archive is named before the checksum

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/commands/install_tools.py`, `Dockerfile`
- Tests: `tests/ci/test_release_download_retries.py`, `tests/commands/test_install_tools.py`, `tests/invariants/test_service_image.py`
- Callers that gain the retry with no edit: the `Dockerfile` (`openspec`, `promtool`, `kubectl`, `helm`), `ci.yml`, `pr-title.yml`, `copilot-setup-steps.yml` and the composite actions `devcontainer-smoke` and `devcontainer-image`.
- No setting and no variable is added, so no ConfigMap rollout. The image digests do not change.

## Feasibility

The premise was checked in the checkout at origin/main (commit 7411967a) and against upstream files.

- `Dockerfile` lines 23 to 26 hold two `ADD --checksum=sha256:... https://github.com/cli/cli/releases/download/v2.102.1/...` steps. BuildKit `ADD` takes `--checksum` but no retry option. Confirmed by reading the file and the test `test_the_dockerfile_fetches_no_remote_file_with_add`, which fails on origin/main with both `ADD` lines.
- `_download` in `install_tools.py` makes one `get` and then `raise_for_status`. `_download_client` calls `http_client(EgressLevel.PUBLIC, follow_redirects=True, event_hooks=...)` with no `retries=`. The test `test_install_retries_two_504_answers_then_installs_the_archive` fails on origin/main with `HTTPStatusError: Server error '504 Gateway Timeout'`.
- `http_client(retries=N)` in `src/devops_cli/http/entry.py` wraps the transport in `create_retry_transport` (`src/devops_cli/ai/retries/__init__.py`, tenacity). It retries 429, 5xx and `httpx2.TransportError`, waits `wait_exponential(multiplier=1, max=60)` with `Retry-After`, and re-raises the last error. A 404 raises at once. The test `test_a_404_answer_is_not_retried` proves it. Eight tries wait 1, 2, 4, 8, 16, 32 and 60 seconds: 123 seconds in all. The default of 5 tries waits 15 seconds in all, too short for an outage.
- All the callers listed in Impact call the same `install_binary`, so one change covers them. Only the health checks in `ci.yml` and `release.yml` use `curl --retry` today, and they test the local service, not a release download. The test over the workflows and composite actions found no other `curl` or `wget` without a retry option.
- `aquasecurity/trivy-action` v0.36.0 (commit `ed142fd0`, `action.yaml` read from GitHub) has the input `skip-setup-trivy`. It has no retry input. Unless the input is true, it calls `aquasecurity/setup-trivy` v0.2.6, which restores a cache and on a miss runs `contrib/install.sh` of the Trivy repository. The image jobs have no `uv`, so a change to the six scan steps needs a new setup step in each job and changes `test_every_trivy_scan_runs_the_trivy_tools_lock_pins`. That is separate work: no open issue covered it, and #4229 now does. The scan of the static job already uses `devops install-tools --tool trivy`, which gains the retry.
- The builder stage of the `Dockerfile` is `python:3.14-slim-trixie`, which has no `curl`. The `gh` pin has no entry in `tools.lock`, so `devops install-tools` cannot fetch it. A `[binary.gh]` entry would also change the runner tool table (`NOT_IN_RUNNER` and `ToolSource`), the install of `gh` in the devcontainer (the `github-cli` feature installs it already), and the tests that read the `Dockerfile` for the `gh` release. The `curl` step needs one apt package in a stage that no image ships. See the design.
- No duplicate exists. A search of open issues for download and retry finds #3612, which covers the fetch of the devcontainer features and not these downloads. No open or merged pull request touches `install_tools.py` or the download lines of the `Dockerfile` since #4182.

## Existing Tool Considered

- `http_client(retries=N)` of the project covers `install_tools.py` with tenacity, a dependency already. It adds no module and no library.
- `curl --retry 8 --retry-all-errors --retry-delay 2 --fail` with `sha256sum -c` covers the `Dockerfile`. `curl` and `sha256sum` are standard tools, and the `runner` stage installs `curl` from apt already.
- For the body check, the standard library recognizes the formats: the magic bytes of gzip (`1f 8b`) and `zipfile.is_zipfile`. No new library.

The change deletes the two `ADD` steps and the `RUN tar` step of the `Dockerfile` that unpacked their files. It builds no retry loop of its own.

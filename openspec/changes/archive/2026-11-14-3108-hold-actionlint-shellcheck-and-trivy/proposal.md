# Proposal: #3108

## Why

The runner image leaves out `actionlint`, `shellcheck` and Trivy, because the image scan fails on a fixed HIGH finding in the newest release of each. The blockers are gone: the maintained actionlint fork `kjanat/actionlint` 1.17.1 updates its Go toolchain and its local binary scans with 0 HIGH or CRITICAL findings, and Trivy 0.76.2 holds go-jose 4.1.6 (CVE-2026-116587 fixed). The image now holds the three tools, so a Job runs the `actionlint` row of `devops ci` and the IaC scan that the pull request checks. Closes #3108.

## What Changes

- Move `actionlint`, `shellcheck` and `trivy` from `NOT_IN_RUNNER` to `RUNNER_TOOLS`, with their sources: the pinned `kjanat/actionlint` image, apt, and `tools.lock`.
- Add the `actionlint` image stage to the `Dockerfile`, copy its binary to the runner, install shellcheck from apt, and install Trivy with `devops install-tools` in the `runner-tools` stage.
- Update the test that held the three out, and the two documents that said the image lacks them.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-runner`: The runner image passes the image scan.

## Impact

- Code: `src/devops_cli/roadmap/runner_tools.py`, `Dockerfile`
- Documents: `docs/CLUSTER.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/roadmap/test_roadmap_runner_tools.py`

## Feasibility

Read on 2026-11-14 against `origin/main` at `04107728d`.

- `actionlint` 1.17.1 of `kjanat/actionlint` (2026-11-09) says it "updates the Go toolchain and container packages to address the vulnerabilities reported in #356". `trivy rootfs --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 /usr/local/bin/actionlint` reports 0 findings on the binary of the pinned image.
- Trivy 0.76.2 (2026-11-05) says "`github.com/go-jose/go-jose/v4` is bumped to v4.1.6, fixing GHSA-mgcc-cww5-fp2q" and `golang.org/x/net` to v0.62.0; `src/devops_cli/tools_lock/tools.lock:228:version = "0.76.2"` is the pin.
- The devcontainer already pins the actionlint image by digest: `.devcontainer/Dockerfile:3:FROM docker.io/kjanat/actionlint:1.17.1@sha256:c0a63b3e...`.
- The runner image links `/opt/devops-tools/bin` on PATH: `Dockerfile:142:PATH=/app/.venv/bin:/opt/devops-tools/bin:$PATH`.
- The tests of the table pass on the branch: `uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py`.

## Existing Tool Considered

The three tools are existing open tools, and the change adds no new tool and no new dependency. The image scan, `devops install-tools` and the table checks are the project's own tools. The alternative of building actionlint from source would add a Go toolchain and a build stage.

# Tasks

## 1. Build the images from the devtools image

Kind: other. Reads: `Dockerfile`, `.devcontainer/Dockerfile`, `src/devops_cli/ai/mcp/roles.py`. Changes: `Dockerfile`.

- [x] 1.1 Add the `devtools` stage with the digest of `.devcontainer/Dockerfile`, build `runner-deps` FROM it with bind mounts of the `lock` stage, add `runner-builder`, and copy only the project into `runner`
  - Verification: a person runs `docker build --target runner .` and the smoke test of `ci.yml` on the image
- [x] 1.2 Delete the gh download, the actionlint and `runner-tools` stages, each `devops install-tools` run and the `runner_tools` build step
  - Verification: `git grep -n -e install-tools -e releases/download -e sha256sum -- Dockerfile` prints nothing
- [x] 1.3 Build the MCP server image on `service-deps` with kubectl and helm of the devtools image, and the Service image with gh and the pruned OpenSpec tree of the devtools image
  - Verification: a person runs `docker build --target mcp-server .` and the smoke test of `ci.yml` on the image
- [x] 1.4 Run every smoke command of `ci.yml` on the three images with a read-only root, `--tmpfs /home/devops:mode=1777`, `--cap-drop ALL` and `--security-opt no-new-privileges`, and scan them with the flags of `.github/actions/image-scan`

## 2. Smoke tests, scans and Renovate

Kind: other. Reads: `.github/actions/image-scan/action.yml`. Changes: `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/service-image-test.yml`, `.trivyignore.yaml`, `.github/renovate.json`.

- [x] 2.1 Run `kubectl version --client` and `helm version` in the MCP server smoke test, run the runner tool check with no tool path, bound the runner at 7000000000 bytes, and drop `no-cache-filters: runner`, in `ci.yml` and `release.yml`
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
- [x] 2.2 Scan the runner with `exit-code: "0"`, move the kubectl entries of `.trivyignore.yaml` to `usr/local/bin/kubectl`, and drop the entries that only the runner scan read
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
- [x] 2.3 Drop `/opt/devops-tools/bin` from the PATH of `service-image-test.yml`, and set the prefix of the devtools group and the rule descriptions in `.github/renovate.json`
  - Verification: `renovate-config-validator --strict` of Renovate 44.239.2 passes on `.github/renovate.json`
- [x] 2.4 Run `uv run --locked devops ci --check --only openspec` in the copy of the checkout of the runner smoke test, and put the OpenSpec pin of `tools.lock` in the Renovate group `devtools`
  - Verification: a person runs the smoke command on the runner image: it exits 0 with the OpenSpec of the image, and 1 with OpenSpec 2.1.1 first on PATH

## 3. Name the devtools image in the runner tool table

Kind: behavior. Reads: `tests/roadmap/test_roadmap_runner_tools.py`. Changes: `src/devops_cli/roadmap/runner_tools.py`, the tests of `tests/invariants/` that read the `Dockerfile`, `tests/gate/tree_checks/config_reads.toml`.

- [x] 3.1 Name the devtools image as the source of each tool, move kubectl, kube-linter, osv-scanner, npm, zsh and ps to `RUNNER_TOOLS`, and keep in `NOT_IN_RUNNER` only programs that a step of the Job does not count on
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py`
- [x] 3.2 Delete the tests that read the removed Dockerfile lines, and lower their counts in `tests/gate/tree_checks/config_reads.toml`
  - Verification: `$ uv run devops ci test tests/invariants/test_mcp_server_image.py tests/invariants/test_runner_hooks.py tests/invariants/test_runner_image.py tests/invariants/test_service_image.py`
- [x] 3.3 State the true cause in the texts that said the runner holds no kubectl or no container engine: `_NO_CLUSTER`, `tests/conftest.py`, `tests/invariants/test_hermetic_floor.py` and `src/devops_cli/k8s/volume_move_measure.py`, and delete the MCP server test that only tested a fake of `install-tools --check`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py tests/invariants/test_mcp_server_image.py tests/invariants/test_hermetic_floor.py`

## 4. Documents

Kind: other. Changes: `SECURITY.md`, `docs/CLUSTER.md`, `docs/SDLC.md`, `docs/ROADMAP_WORKFLOW.md`.

- [x] 4.1 Add the table of SECURITY.md with the two entries of 2026-11-19, the real exposure of the Job pod and a review date, and update docs/CLUSTER.md, docs/SDLC.md and docs/ROADMAP_WORKFLOW.md
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #4363 removes `devops install-tools` and `tools.lock` from `src/`.
- #6518 gives the runner Job only the keys of the Secret `devops-cli` that it needs.
- #6517 takes the dev dependencies out of the runner image and bootstraps them with uv.
- A follow-up moves `tools.lock` and the devtools image to OpenSpec 2.1.1 and shortens the three MODIFIED requirements that 2.1.1 refuses.
- #1858, #6407 and #6408 rebase onto this change.
- Pending a person: close #6263, #5394 and #3562 after the merge, because the runner holds the review scanners, kube-linter and kubectl.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

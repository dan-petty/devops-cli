# Tasks

## 1. Merge the two image jobs into one bake job

Kind: other. Reads: `.github/workflows/ci.yml`, `Dockerfile`, `docs/CLUSTER.md`. Changes: `.github/workflows/ci.yml`.

- [ ] 1.1 Edit `.github/workflows/ci.yml`: delete the job `runner-image` and move its steps `Run Runner Image Smoke Test` and `Scan Runner Image for Vulnerabilities` into the job `mcp-server-image`, after that job's MCP server scan step. Set the merged job's name to `Runner Image` and its `timeout-minutes` to 18, and keep its `runs-on`, its `permissions`, its `if` condition, its checkout step, its `Detect Image Content Changes` step with the same `IMAGE_CONTENT_PATHS`, and its `Set up Docker Buildx` step. Add the step `Write Docker Bake Definition` before the bake step to write `docker-bake.hcl` with targets `runner` and `mcp-server`: `context = "."`, `dockerfile = "Dockerfile"`, `target` of the same name, `tags = ["devops-cli-runner:local"]` or `tags = ["devops-cli-mcp-server:local"]`, and `cache-from = ["type=registry,ref=ghcr.io/${{ github.repository }}/runner:buildcache"]` or its `mcp-server` sibling, with `no-cache-filter = ["mcp-server"]` on the `mcp-server` target only. Replace the step `Build and Load MCP Server Image` with the step `Build and Load Runner and MCP Server Images`, which uses `docker/bake-action@59cb1203cd42bcefd40a1b6d73b589e48c86040e # v7.5.0`, sets `timeout-minutes: 12`, `load: true` and `push: false`, passes `targets` with `runner` and `mcp-server`, and passes `files: docker-bake.hcl`. Keep the two smoke-test steps and the two scan steps with the condition `steps.image_changes.outputs.changed == 'true'`, the runner scan's `exit-code: "0"` and the categories `trivy-image-runner` and `trivy-image-mcp-server`. Rewrite the comment above the merged job: one job builds both targets with one bake call, so a push starts one hosted job fewer, and each target keeps its own registry cache
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor` passes

## 2. Read the merged job in the image invariants

Kind: other. Reads: `.github/workflows/ci.yml`, `tests/invariants/test_runner_image.py`, `tests/invariants/test_mcp_server_image.py`, `tests/invariants/test_architectural_invariants.py`. Changes: `tests/invariants/test_runner_image.py`, `tests/invariants/test_mcp_server_image.py`, `tests/invariants/test_architectural_invariants.py`.

- [ ] 2.1 Edit `tests/invariants/test_runner_image.py`: put the name `Build and Load Runner and MCP Server Images` in place of `Build and Load Runner Image` in the tuple `RUNNER_STEPS`, read the job `mcp-server-image` in `test_the_pull_request_check_builds_the_runner_image_and_pushes_nothing`, and assert that the step's `with.files` is `docker-bake.hcl` and `Write Docker Bake Definition`'s `run` holds `target "runner"` and the runner `cache-from` ref, while the `if`, the `permissions`, the `push`, the `load`, the three step conditions and the empty `needs` stay. Edit `tests/invariants/test_mcp_server_image.py`: read the step `Build and Load Runner and MCP Server Images` of the same job, assert that its `with.files` is `docker-bake.hcl` and `Write Docker Bake Definition`'s `run` holds `target "mcp-server"`, and keep the assertion that the smoke test bounds the image at 3000000000 bytes. Edit `tests/invariants/test_architectural_invariants.py`: drop the parameter whose job is the deleted `runner-image` from `test_image_path_filter_covers_dockerfile_sources`, because the merged job declares the one `IMAGE_CONTENT_PATHS` list that both targets read
  - Verification: `$ uv run devops ci test tests/invariants` passes

## 3. Allowlist the run steps of the merged job

Kind: other. Reads: `tests/commands/test_ci.py`, `.github/workflows/ci.yml`. Changes: `tests/commands/test_ci.py`.

- [ ] 3.1 Edit the allowlist of `_validate_ci_workflow_parity` in `tests/commands/test_ci.py`, the allowlist that `test_ci_workflow_parity_with_check_table` runs over `.github/workflows/ci.yml`: delete the two entries of the job `runner-image`, which name the steps `Detect Image Content Changes` and `Run Runner Image Smoke Test`, and add the entries that pair the job `mcp-server-image` with the steps `Write Docker Bake Definition` and `Run Runner Image Smoke Test`, with their reasons. The entries of `mcp-server-image` for its own detect and smoke-test steps stay, and the bake step and the two scan steps need no entry because they run no command
  - Verification: `$ uv run devops ci test tests/commands/test_ci.py` passes

## Criteria

- Group 1: One job per push builds both images.
- Group 1: The `runner` stage builds one time.
- Group 1: Both smoke tests and both scans run.

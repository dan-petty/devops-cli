# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests: the release job, the same smoke test and scan, and the check that each image in `k8s/` has a publish job
  - Verification: `$ uv run devops ci fail-to-pass --base origin/main` shows the tests fail before the change and pass after it
- [x] 1.2 Add job `mcp-server-image` to `release.yml`
  - Verification: `$ uv run devops ci test tests/invariants/test_mcp_server_image.py tests/invariants/test_workflow_contracts.py tests/invariants/test_k8s_manifests.py`

## 2. Documents

- [x] 2.1 List the job in `RELEASE_CYCLE.md` and the person step in `k8s/README.md`
  - Verification: `$ uv run devops ci docs`

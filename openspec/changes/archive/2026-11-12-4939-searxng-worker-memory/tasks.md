# Tasks

## 1. The SearXNG worker is replaced before the memory limit

Kind: fix. Changes: `tests/invariants/test_k8s_searxng.py`, `k8s/devops/searxng/deployment.yaml`, `k8s/README.md`.

- [x] 1.1 Change the invariant tests first: the environment holds `GRANIAN_WORKERS_MAX_RSS=512`, and the resources are a request of 256 Mi and a limit of 1 Gi. They fail on `origin/main`.
- [x] 1.2 Set the variable and the resources in the Deployment, with the reason in a comment.
- [x] 1.3 Update "The limits" in `k8s/README.md`.
- [x] 1.4 Verify: `uv run pytest tests/invariants/test_k8s_searxng.py` passes, and `uv run devops ci fail-to-pass --base origin/main` shows the two tests fail on the base.

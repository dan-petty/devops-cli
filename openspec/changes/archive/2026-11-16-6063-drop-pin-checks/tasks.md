# Tasks

## 1. SearXNG

- [x] 1.1 Write the failing test that a passing `devops k8s searxng-check` names no image of its own
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_searxng_check.py`
- [x] 1.2 Remove `SEARXNG_IMAGE`, the image of the success message, the gate assertion, the engine-names tests, the saved-reply and image tests, and the two fixtures
  - Verification: `$ uv run devops ci test tests/commands/k8s/test_k8s_searxng_check.py tests/k8s/test_searxng_check.py tests/invariants/test_k8s_searxng.py tests/ai/test_web_search_searxng.py`

## 2. Chart tables

- [x] 2.1 Key `CHART_CLAIMS` and `_CHART_TOKENS` on the chart name, and compare the chart names in their tests
  - Verification: `$ uv run devops ci test tests/core/test_k8s_local_path_placement.py tests/invariants/test_k8s_manifests.py`

## 3. Documents

- [x] 3.1 Update the SearXNG note of `.github/renovate.json`, remove its test, and update `docs/CLUSTER.md` and `k8s/README.md`
  - Verification: `$ uv run devops ci docs`

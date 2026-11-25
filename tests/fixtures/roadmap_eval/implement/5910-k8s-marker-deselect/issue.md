## Problem

A default test run deselects every test under `tests/k8s/`: 819 tests, offline tests included. `_deselect_by_marker(config, items, "k8s")` in `tests/conftest.py` (from #4007, commit 729dbeb8f, 2026-11-15) checks `"k8s" in item.keywords`. pytest puts the name of each parent package in the keywords, so the package `tests/k8s` matches, and not only the tests marked `k8s`. With `-m k8s` the tests are deselected too, because they carry no mark.

Evidence on origin/main (0.159.0):

- `uv run pytest -n 0 --co -q tests/k8s/` prints `no tests collected (819 deselected)`.
- `uv run devops ci test tests/k8s/test_k8s_configmap.py` prints `21 deselected / 0 selected`.
- `uv run pytest -n 0 -m "k8s or not k8s" tests/k8s/test_k8s_configmap.py` runs the 21 tests.

So CI has run no test of `tests/k8s/` since 2026-11-15, and a change that breaks one passes the checks. #5903 found this when it changed `k8s/devops/configmap.example.yaml`.

## Expected behavior

- A default run deselects only the tests that carry the mark `k8s`, for example with `item.get_closest_marker("k8s")`.
- The offline tests under `tests/k8s/` run in CI again.
- A test fails if a default run deselects a test that has no `k8s` mark.


Source: https://github.com/dan-petty/devops-cli/issues/5903

<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P1-High", "Status": "In Review", "Value": "High"} -->

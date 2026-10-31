# Tasks

## 1. Write Failing Tests
- [x] Add failing test cases in `tests/test_github_metrics.py` asserting one DEBUG line, zero WARNING lines, and `traffic_collected=False` when traffic calls return integration 403 <!-- id: 1-failing-tests -->
- [x] Verify test fails against current `origin/main` <!-- id: 1-verify-fail -->

## 2. Implement Integration 403 Handling
- [x] Update `_read_json` and `get_repository_traffic_metrics` in `src/devops_cli/github/metrics.py` to suppress WARNING and emit one DEBUG line on integration 403 <!-- id: 2-update-metrics -->
- [x] Set `traffic_collected=False` when traffic endpoints are refused by the token <!-- id: 2-skip-gauges -->
- [x] Verify tests pass <!-- id: 2-verify-pass -->

## 3. Verification & PR
- [x] Run `devops ci fail-to-pass --base origin/main` <!-- id: 3-fail-to-pass -->
- [x] Run fast checks, archive change, and open draft PR <!-- id: 3-pr -->
- [x] Monitor checks and mark PR ready <!-- id: 3-ready -->

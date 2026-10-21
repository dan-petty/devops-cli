# Task #1495: Toolchain Cache Node 24 Pin and Single `setup-uv` Cache Writer

**Issue**: [#1495](https://github.com/dan-petty/devops-cli/issues/1495)
**Feasibility**: Confirmed against `.github/actions/setup-toolchain/action.yml`, `.github/workflows/ci.yml`, and `.github/workflows/release.yml`. `actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9` (v6.1.0) declares `using: 'node24'`, and `astral-sh/setup-uv` supports `save-cache` to disable cache saving in concurrent jobs that share the same lockfile cache key.

## Deliverables

- [x] Pin `actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9 # v6.1.0` in `.github/actions/setup-toolchain/action.yml`.
- [x] Add `save-uv-cache` input (default `"true"`) to `.github/actions/setup-toolchain/action.yml` and pass it to `astral-sh/setup-uv`'s `save-cache`.
- [x] Set `save-uv-cache: "false"` on non-`static` pull request / push jobs in `.github/workflows/ci.yml` (`test`, `changed-tests`, `rule-pack`) and `save-cache: false` on `setup-uv` steps in `.github/workflows/release.yml`.
- [x] Add `test_toolchain_cache_runs_on_node24_and_one_job_per_event_saves_uv_cache` in `tests/test_ci.py` asserting the `actions/cache` v6.1.0 pin and that at most one job per `pull_request` or `push` event saves the `setup-uv` cache across `ci.yml` and `release.yml`.

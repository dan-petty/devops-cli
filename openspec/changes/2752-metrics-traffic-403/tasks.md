# Tasks

## 1. The Service asks for no traffic, and a refused path is asked once

- [x] 1.1 Add failing tests. In `tests/test_github_metrics.py`: a collection under the App sends no traffic request and no traffic point but sends the stars and the forks; a collection from a workstation sends the four; two collections after a 403 send the refused path once; another repository, a 502 and a 403 of another message do not set the guard; `devops gh metrics` prints "not collected". In `tests/test_github_errors.py`: `is_gh_refused_by_token`. In `tests/test_roadmap_run.py`: the metrics row under the App sends no traffic request. Give `GitHubFake` a `refused_traffic` option and reset the guard in `tests/conftest.py`
  - Verification: `uv run devops ci test tests/test_github_metrics.py tests/test_github_errors.py tests/test_roadmap_run.py` fails on the base
- [x] 1.2 Add `is_gh_refused_by_token` to `github/error_classifier.py` and its phrase to `config/constants.py`. In `github/metrics.py` add `TrafficSummaryMetric.traffic_collected`, the guard with `reset_refused_paths`, and `_read_json`; replace the five `_fetch_*` copies of the `try` block with it; skip the traffic reads and the six series when `acts_as_github_app()`. Print "not collected" in `commands/gh.py`
  - Verification: `uv run devops ci test tests/test_github_metrics.py tests/test_github_errors.py tests/test_roadmap_run.py`
- [x] 1.3 Run `uv run ruff check`, `uv run ruff format --check` and `uv run mypy --strict` on the changed files
  - Verification: `uv run devops ci lint`

## 2. Documentation

- [x] 2.1 Say in the six instrument descriptions that the Service does not send the traffic gauges, and add the consequence to ADR 0015. Run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
- Pending a person: decide whether the metrics row gets its own token with Administration (read), as ADR 0015 allows. This change does not add the permission.

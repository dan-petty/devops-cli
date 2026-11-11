# Tasks

## 1. Behavior: one series for each repository

- [x] 1.1 Add the failing tests: two repositories in one process give one series of each project instrument for each repository, each with its own stars; a second repository sends no 0 for the label sets of the first; a label set that leaves one repository gets one 0 for that repository only; the command refuses `--milestone` and `--limit 5` with `--emit-telemetry` before any request and sends `--limit 10`; each project instrument description names `repo`
  - Verification: `$ uv run devops ci test tests/github/test_github_metrics.py tests/telemetry/test_telemetry_instruments.py`
- [x] 1.2 Add `repo` to each point of `emit_project_metrics_telemetry`, key `_sent_item_series` by `repo`, add the guard and its message to `devops gh metrics`, share `DEFAULT_PROJECT_METRICS_RELEASE_LIMIT`, and name `repo` in the instrument descriptions
  - Verification: `$ uv run devops ci test tests/github/test_github_metrics.py tests/telemetry/test_telemetry_instruments.py tests/roadmap/test_roadmap_run_metrics.py`

## 2. Documents

- [x] 2.1 Say in `docs/TELEMETRY.md` what the `repo` label of the project series holds and that the command refuses a filtered snapshot, and regenerate the documentation
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- The project-metrics dashboard item adds the `job` and `repo` variables and the filter to every query of `project-metrics.json`.
- Pending a person: 24 h after the rollout, check that `count by (repo) (last_over_time(devops_cli_project_items{job="roadmap-service"}[1h]))` gives one series for each managed repository, and that the stars value of the devops-cli repository equals `stargazers_count`. The pull request comment gives the steps.

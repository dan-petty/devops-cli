# Tasks

## 1. Add the `charts` row of `devops ci`

Kind: behavior. Reads: `src/devops_cli/commands/ci.py`, `tests/commands/test_ci_gate_rows.py`, `tests/gate/k8s.py`. Changes: `tests/commands/test_ci_gate_rows.py`, `src/devops_cli/commands/ci.py`, `src/devops_cli/lang/en/messages.py`, `tests/gate/charts.py` (new), `tests/gate/charts_checks/__init__.py` (new).

- [x] 1.1 Add the row `charts` to `_GATE_ROWS` of `tests/commands/test_ci_gate_rows.py`, after `k8s`. The tests fail, because the table of `devops ci` has no row `charts`
  - Verification: `$ uv run devops ci test tests/commands/test_ci_gate_rows.py` fails
- [x] 1.2 Add the row `charts` after `k8s` to `CHECK_ROW_NAMES` and to `get_check_specs`, with the title `MESSAGES.ci.chart_renders`. Add `tests/gate/charts.py`, which runs the checks of `tests/gate/charts_checks/`
  - Verification: `$ uv run devops ci test tests/commands/test_ci_gate_rows.py`

## 2. Check the rendered Tempo configuration with the Tempo image of the chart

Kind: other. Reads: `k8s/argocd/apps/tempo.yaml`, `src/devops_cli/k8s/image_pins.py`, `src/devops_cli/k8s/app_sources.py`, `tests/gate/k8s_render.py`, `tests/gate/k8s_checks/tempo_query_limits.py`. Changes: `tests/gate/charts_render.py` (new), `tests/gate/charts_checks/tempo_config.py` (new), `tests/gate/charts_checks/tempo_query_limits.py` (moved from `tests/gate/k8s_checks/`).

- [x] 2.1 Add `chart_objects` to `tests/gate/charts_render.py`: it renders the chart source of an Argo CD Application with `helm template`, as `devops k8s image-pins` does, once for each process. Add `check_the_rendered_tempo_config_parses_with_the_tempo_image_of_the_chart` in `tests/gate/charts_checks/tempo_config.py`: it writes the rendered ConfigMaps that the `tempo` container mounts and starts its image with its arguments and `-config.verify=true`. Move `tempo_query_limits.py` to `tests/gate/charts_checks/`, and change it to assert the bounds of #6616 on the rendered configuration and the rendered memory limit. The row fails on the values of main
  - Verification: `$ uv run devops ci --check --only charts` fails, and shows `field max_bytes_per_trace not found in type frontend.SearchConfig`
- [x] 2.2 Keep `tests/gate/k8s.py` and `tests/gate/k8s_render.py` as on main, so the `k8s` row starts no `helm` and no `docker`
  - Verification: `$ uv run devops ci --check --only k8s` passes with a `helm` and a `docker` first on PATH that exit 1

## 3. Put the Tempo limits under the keys of Tempo 3.1.1

Kind: other. Reads: `k8s/otel/tempo-values.yaml`. Changes: `k8s/otel/tempo-values.yaml`.

- [x] 3.1 Remove `queryFrontend.search.max_bytes_per_trace` and `queryFrontend.search.target_bytes_per_second`, replace `queryFrontend.search.max_duration: 30s` with `queryFrontend.api_timeout: 30s`, and move `global_overrides.max_bytes_per_trace` to `overrides.defaults.global.max_bytes_per_trace`, with comments that name the Tempo 3.1.1 meaning of each key
  - Verification: `$ uv run devops ci --check --only charts`

## 4. Keep the runner tools true

Kind: other. Reads: `src/devops_cli/roadmap/runner_tools.py`. Changes: `src/devops_cli/roadmap/runner_tools.py`.

- [x] 4.1 Give `helm` and `docker` in `NOT_IN_RUNNER` a reason that names the `charts` row, says that the Static Analysis job runs it and that a Job cannot run it, and tells a plan not to name the row in a verification command
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py tests/roadmap/stage/test_roadmap_stage_context.py`

## Workflow follow-up

- Pending a person: after the merge and the sync of Argo CD, check that `otel/tempo-0` is Running and Ready, that Application `tempo` is Synced and Healthy, and that a TraceQL search through Grafana returns traces.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

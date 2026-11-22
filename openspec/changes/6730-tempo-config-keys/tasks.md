# Tasks

## 1. Check the rendered Tempo configuration with the Tempo image of the chart

Kind: other. Reads: `k8s/argocd/apps/tempo.yaml`, `src/devops_cli/k8s/image_pins.py`, `src/devops_cli/k8s/app_sources.py`, `tests/gate/k8s_render.py`, `tests/gate/k8s_checks/tempo_query_limits.py`. Changes: `tests/gate/k8s_render.py`, `tests/gate/k8s.py`, `tests/gate/k8s_checks/tempo_config.py` (new), `tests/gate/k8s_checks/tempo_query_limits.py`.

- [ ] 1.1 Add `chart_objects` to `tests/gate/k8s_render.py`: it renders the chart source of an Argo CD Application with `helm template`, as `devops k8s image-pins` does, once for each process. Add `check_the_rendered_tempo_config_parses_with_the_tempo_image_of_the_chart` in `tests/gate/k8s_checks/tempo_config.py`: it writes the rendered ConfigMaps that the `tempo` container mounts and starts its image with its arguments and `-config.verify=true`. Change `tests/gate/k8s_checks/tempo_query_limits.py` to assert the bounds of #6616 on the rendered configuration and the rendered memory limit. The row fails on the values of main
  - Verification: `$ uv run devops ci --check --only k8s` fails, and shows `field max_bytes_per_trace not found in type frontend.SearchConfig`

## 2. Put the Tempo limits under the keys of Tempo 3.1.1

Kind: other. Reads: `k8s/otel/tempo-values.yaml`. Changes: `k8s/otel/tempo-values.yaml`.

- [ ] 2.1 Remove `queryFrontend.search.max_bytes_per_trace` and `queryFrontend.search.target_bytes_per_second`, replace `queryFrontend.search.max_duration: 30s` with `queryFrontend.api_timeout: 30s`, and move `global_overrides.max_bytes_per_trace` to `overrides.defaults.global.max_bytes_per_trace`, with comments that name the Tempo 3.1.1 meaning of each key
  - Verification: `$ uv run devops ci --check --only k8s`

## 3. Keep the runner tools true

Kind: other. Reads: `src/devops_cli/roadmap/runner_tools.py`. Changes: `src/devops_cli/roadmap/runner_tools.py`.

- [ ] 3.1 Give `helm` and `docker` in `NOT_IN_RUNNER` a reason that names the Tempo checks of the `k8s` row, and says that no step of a Job runs that row
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_runner_tools.py`

## Workflow follow-up

- Pending a person: after the merge and the sync of Argo CD, check that `otel/tempo-0` is Running and Ready, that Application `tempo` is Synced and Healthy, and that a TraceQL search through Grafana returns traces.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

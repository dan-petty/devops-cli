## ADDED Requirements

### Requirement: The GPU row shows SM activity and SM occupancy
The GPU row of the LLM stack dashboard `k8s/monitoring/dashboards/llm-stack.json` SHALL hold the panel `GPU SM Activity and Occupancy` with unit `percentunit`, min 0 and max 1, one target for each of `DCGM_FI_PROF_SM_ACTIVE` and `DCGM_FI_PROF_SM_OCCUPANCY` aggregated `avg by (hostname, gpu, modelName)`, and a description that names the cards that report no profiling field.

#### Scenario: The render holds the panel in the GPU row
- **WHEN** `uv run devops ci --check --only k8s` renders the environment tree
- **THEN** the `grafana-stack-dashboards` ConfigMap holds the panel at `gridPos.y` 83 between the GPU row and the Qdrant row, and `uv run devops grafana dashboards lint k8s/monitoring/dashboards` reports zero errors

#### Scenario: The rendered panel holds the two targets and the description
- **WHEN** `uv run devops ci --check --only k8s` renders the environment tree
- **THEN** the panel holds unit `percentunit`, min 0 and max 1, the targets `avg by (hostname, gpu, modelName) (DCGM_FI_PROF_SM_ACTIVE)` and `avg by (hostname, gpu, modelName) (DCGM_FI_PROF_SM_OCCUPANCY)`, and a description that names `Quadro P6000` and `GeForce RTX 3090`

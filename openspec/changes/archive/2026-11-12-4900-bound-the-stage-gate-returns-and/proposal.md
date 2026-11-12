# Proposal: #4900

## Why

#4869 (for #4802) made the returns of a refused stage reply a setting, `roadmap.stage.gate_returns`, with the default 3. The setting has a lower limit and no upper limit, and the return loop `_Planner._returned` does not read the stop of the Service. Each return is one more plan run, so a ConfigMap value of 10 gives one item 34 plan runs, and a return can start during the 600 s drain. A plan run sends model requests, and the cut at the end of the drain refuses only GitHub requests, so it does not stop the run. The owner allowance to loosen the roadmap caps asks for a hard ceiling for each cap, and the owner rule of nested timeouts asks that an inner limit ends before the limit around it. Closes #4900.

## What Changes

- `CONST_ROADMAP_STAGE_GATE_RETURNS_CEILING` (3) is the upper limit of `roadmap.stage.gate_returns`. The settings load refuses a higher value.
- After the Service stops, the stage job starts no return of a refused reply. The round ends with `ServiceStoppingError`, as the stop before an item does, and records no failure for the item.
- The settings description, `docs/roadmap/stage.md`, `k8s/README.md` and the docstrings state the ceiling and the stop.

## Capabilities

- `roadmap-stage`: the returns of a refused reply have a hard ceiling of 3 and do not start after the Service stops.

## Impact

- An item makes at most 13 plan runs with a review and 5 with no review. The default of 3 does not change, and the live ConfigMap does not set the setting, so the rollout loads as before.
- A pod that drains ends its stage round before the next return, and not by SIGKILL after 660 s. The next pod takes the item again.
- #4851 can raise the ceiling when it adds its bounded extension of the returns.

## Feasibility

- `RoadmapStageConfig.gate_returns` in `src/devops_cli/config/settings.py` has `ge=0` and no `le`: `RoadmapStageConfig(gate_returns=50)` loads on `main` at c3130a343.
- `_Planner._returned` in `src/devops_cli/roadmap/stage/stage.py` stops only at `returns >= self._gate_returns`. The only stop check of the stage job is `raise_if_service_stops` before each item in `_plan_each`.
- `ServiceStoppingError` is a `RoadmapRunError`. `_plan_each` catches `AIClientError`, `RoadmapStageError` and `ToolExecutionError` only, so the error from inside `plan` ends the round through the stop path of #2753, as a stop that the request budget raises inside a plan run does today.
- `k8s/README.md` item 22: the drain is 600 s, the cut at the next GitHub request is 30 s, and the grace is 660 s. The p90 of one plan ask was about 728 s on 2026-11-11.
- `kubectl -n devops get configmap devops-cli-config` holds no `gate_returns` key on 2026-11-12, so the ceiling cannot fail the load of the live Service.
- The time guard before a return (item seconds plus one ask within a limit) needs an outer deadline that the stage job does not have yet. #4847 adds the guards of the cap points, and this change does not add it.

## Existing Tool Considered

pydantic's `Field(le=...)` holds the ceiling, and the existing `raise_if_service_stops` of #4485 holds the stop. No new library. Cost to build: about 150,000 tokens and 2 hours.

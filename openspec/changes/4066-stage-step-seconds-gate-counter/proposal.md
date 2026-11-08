# Proposal

## Why

The stage job has one metric, `devops_cli_roadmap_stage_total`, with the label `result` only. No metric shows how long each step of a stage round takes, so a slow step hides in the seconds of the whole row (#4058). No counter shows which gate refused a plan: `check_proposal` joins the problems of all gates, and the name of the gate is lost (#4066). This is wave 8 of the staging plan in the tracker #3027.

## What Changes

- Declare the histogram `devops_cli_roadmap_step_seconds` (unit `s`) in `src/devops_cli/telemetry/instruments.py` with the labels `repo`, `row`, `step` and `result`, and add it to `INSTRUMENTS` and `__all__`. The label scheme is shared with #4067, which sends the implement row through the same instrument.
- Declare the counter `devops_cli_roadmap_stage_gate_refusals_total` (unit `1`) with the labels `repo` and `gate`.
- Add `SELECT`, `GATE` and `REVIEW` to `StepName` in `src/devops_cli/roadmap/failure.py`. `PLAN` and `APPLY` exist from #4056.
- Time each call of a stage step with the clock seam `devops_cli.core.clock.monotonic` and send one sample when the call ends, with the result `ok` or `error`. `select` is the read of the selection in `plan_stage`, `plan` is each model call of the planner, `gate` is each call of the gates, `review` is each model review of the verifier, and `apply` is the write of one item in the stage writer.
- In the planner, call `check_gates` where `check_proposal` is called and add 1 for each gate with a problem, under `repo` and the `ProposalGate` value. A gate that finds a problem is a refusal and not an error: the gate sample has the result `ok`.
- A replay of the golden set (`plan_item`) has no repository and sends no sample.
- Regenerate `docs/TELEMETRY.md` with `uv run devops docs generate --sync-readme`. The rows state the series counts.
- Series count of the histogram: 1 repository x 1 row x 5 steps x 2 results = at most 10 series. The histogram is exponential, which Prometheus 3 stores as one native histogram for each series, so the buckets add none (see the change that added `devops_cli_roadmap_row_seconds`). The issue text "times the histogram buckets" does not hold for this path.
- Series count of the counter: 1 repository x 15 gates = 15 series. The issue says 14 gates; `ProposalGate` has 15 members, and the tests read the count from the enum.
- `StepName` gains three members, so the requirement "A step has a name" of `roadmap-failure-taxonomy` changes. The change adds no field to a persisted file: the ledger of the stage job stores the string of `stage.failed_step`, and the new members are metric labels that no record holds. A test still loads an old record with the step `plan`.
- Rollout: the change adds, removes, renames and tightens no setting. `k8s/devops/configmap.example.yaml` and the live ConfigMap load as before, and `tests/config/test_k8s_devops_runtime.py` already loads the example ConfigMap into `Settings`. `Settings` has `model_config` with `extra="ignore"` (`src/devops_cli/config/settings.py`), as have `RoadmapConfig` and `RoadmapStageConfig`, so a key that the model does not know is dropped and is not an error. The change applies nothing to the cluster.
- The change carries spec deltas, because a metric of the Service is observable behavior.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `metric-instruments`: The step seconds histogram and the gate refusal counter are declared, documented and sent
- `roadmap-failure-taxonomy`: A step has a name

## Impact

- Code: `src/devops_cli/telemetry/instruments.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/roadmap/step_metrics.py` (new), `src/devops_cli/roadmap/stage/stage.py`
- Documents: `docs/TELEMETRY.md` (generated)
- Tests: `tests/telemetry/test_roadmap_stage_steps.py`, `tests/roadmap/test_roadmap_failure.py`

## Feasibility

- Code read at origin/main `7ce8001a`, no run of the Service and no model run: `ROADMAP_ROW_SECONDS` in `src/devops_cli/telemetry/instruments.py` is the pattern of a histogram, and `_observe_row` in `src/devops_cli/roadmap/run.py` times a call with `clock.monotonic()` and sends it with `emit()`. #4058 (row seconds) and #4056 (`StepName.PLAN` and `APPLY`) are merged.
- The sites in `src/devops_cli/roadmap/stage/stage.py`: `select` is `read_stage_selection`, called by `plan_stage`. `plan` is `_Planner._ask`, called from `_gated` and `_repaired`. `gate` is `_Planner._problems`, the one stage caller of `check_proposal`; the other callers (`implement/implement.py`, `roadmap/plan_check.py`) are not a stage round and must not send. `review` is `_Planner._review`. `apply` is `StageWriter._stage`, inside `write_each`, which records a `StageFailure` for a `DevOpsCLIError`.
- `check_proposal` joins the lists that `check_gates` returns (`dict[ProposalGate, list[str]]`), so the gate name is available without new gate logic.
- A gate runs more than once for an item: for the first reply, for a split of it, for the reply that answers a refusal and for each repair round. So the gate samples and the refusals are counts of calls and not of items, and the documentation says so.
- `StepName` has `PLAN`, `APPLY`, `INVESTIGATE` and `PLACE` (`src/devops_cli/roadmap/failure.py`). The living spec `roadmap-failure-taxonomy` lists exactly those four, so the change carries a MODIFIED delta for that requirement. The stage job writes `failure.step.value` to `stage.failed_step` (`StageRecordKey.FAILED_STEP`) and nothing parses `StepName` from storage, so no persisted field changes.
- `ProposalGate` has 15 members: spec-delta, content, citation, form, eval-replay, paths, what-changes, move-prefix, move-verify, search, criteria, dependencies, creates, registry, constants.
- The label `row` and not `job` follows `tool_metrics.start_run(row=...)` and the rule "No instrument attribute is named job or instance" of `metric-instruments`.
- `docs/TELEMETRY.md` is generated by `generate_telemetry_docs` in `src/devops_cli/docs/generator.py` from `INSTRUMENTS`, so the document needs no hand edit.
- The file `svc_issues/c11a2.md` that the task names as basis is not in the repository. The body of #4066 holds the basis, and this change reads it.
- The tests of this change fail on origin/main for the right reasons: the instruments are not declared, `StepName` has no `select`, `gate` or `review`, and a stage round sends no sample. The tests that pass on the base are guards: a golden-set replay sends nothing, a plan that passes every gate adds no refusal, and an old record with the step `plan` still loads.
- Precondition: the calls need a checkout of the repository. They need no network, no cluster and no model.

## Existing Tool Considered

The OpenTelemetry histogram and counter that `emit()` in `src/devops_cli/telemetry/instruments.py` already sends, and the clock seam `devops_cli.core.clock`. No new library. The change adds one small context manager in `src/devops_cli/roadmap/step_metrics.py` that times a step and sends the sample, because five sites in the stage job and the implement sites of #4067 need the same four labels; a try and finally block at each site would repeat them. It deletes no internal code. The cost written by the issue: about 50k tokens and 2.5 hours to build, 3k tokens each quarter to keep, and 10k tokens and 0.5 hours to fix.

# Tasks

## 1. Give a refused reply one extra return while the plan improves

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_findings.py`, `src/devops_cli/roadmap/stage/stage_finding_classes.json`, `src/devops_cli/roadmap/service_stop.py`. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/round_log.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_eval_render.py`, `src/devops_cli/roadmap/stage/stage_findings.py`, `src/devops_cli/telemetry/instruments.py`, `tests/roadmap/stage/test_roadmap_stage_gate_extension.py` (new), `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/stage/test_roadmap_stage_plan_defect_limit.py`, `tests/roadmap/test_roadmap_limit_classes.py`.

- [x] 1.1 Write the tests first in `tests/roadmap/stage/test_roadmap_stage_gate_extension.py`: the gate findings of #5136 as a fixture with the counts of its log lines, the rule extends its last reply, a finding that stays (the stale test path of #4472) or a `never` code stops the reply, an item gets one extra return, the stage job stages the #5136 sequence with 5 planner requests and one line and count for the decision and for the end, the failure names the stop, the setting moves the decision, no extra return starts after the Service stops, and the dry run of `devops roadmap eval stage` counts the extra plan run
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_gate_extension.py`
- [x] 1.2 Add `CONST_ROADMAP_STAGE_GATE_RETURN_EXTENSIONS`, `GateExtension`, `ExtensionEnd` and `gate_extension`, the lines `stage gate extension:` and `stage gate extension end:`, the counters `devops_cli_roadmap_stage_gate_extension_total` and `devops_cli_roadmap_stage_gate_extension_ends_total`, the stop texts, and the rule in the description of `roadmap.stage.gate_returns`, and call the rule in `StageJob._returned` at the last return. Count the extra plan run in the dry run of `devops roadmap eval stage`. Class the new limit in `tests/roadmap/test_roadmap_limit_classes.py`, and change the two tests of `tests/roadmap/stage/test_roadmap_stage_plan.py` that read the old failure text or the old count of requests, and the test of `tests/roadmap/stage/test_roadmap_stage_plan_defect_limit.py` that reads the old failure text. State the reply of the extra return in the description of `devops_cli_roadmap_stage_gate_problems`
  - Verification: `$ uv run devops ci test tests/roadmap/stage tests/roadmap/test_roadmap_limit_classes.py tests/roadmap/steps/test_roadmap_fix_plan.py tests/telemetry`

## 2. Documents

Kind: other. Reads: `docs/roadmap/stage.md`, `docs/CLUSTER.md`. Changes: `docs/roadmap/stage.md`, `docs/CLUSTER.md`, `docs/ENV_VARS.md`, `docs/TELEMETRY.md`.

- [x] 2.1 State the rule, the lines and the counters in `docs/roadmap/stage.md` and `docs/CLUSTER.md`, and regenerate the documents with `devops docs generate`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #5386: the decision model judges the extension through the chain of #4847 and #5272, and a `never` finding refuses a reply at once after the classes are fitted again on replies after #4791.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

# Tasks

## 1. The gates give findings with a gate and a code

Kind: behavior. Changes: `src/devops_cli/roadmap/stage/stage_findings.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_plan_record.py`, `src/devops_cli/roadmap/round_log.py`, `src/devops_cli/telemetry/instruments.py`, `tests/roadmap/stage/test_roadmap_stage_findings.py`, `tests/roadmap/stage/test_roadmap_stage_refused_reply.py`, `tests/roadmap/stage/test_roadmap_stage_repair_return.py`, `tests/telemetry/test_roadmap_stage_steps.py`.

- [x] 1.1 Write the failing tests: each `stage_problem_` message gives its own key as its code, a reply that two gates refuse gives two findings, the joined text of the findings is the joined text of the gates, the counts of a return, the refused file keeps the findings, the two log lines, and the histogram by reply.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_findings.py tests/roadmap/stage/test_roadmap_stage_refused_reply.py tests/roadmap/stage/test_roadmap_stage_repair_return.py tests/telemetry/test_roadmap_stage_steps.py`
- [x] 1.2 Add `stage_findings.py`, keep the findings in the planner and the refused file, log them, and declare `devops_cli_roadmap_stage_gate_problems`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_findings.py tests/roadmap/stage/test_roadmap_stage_refused_reply.py tests/roadmap/stage/test_roadmap_stage_repair_return.py tests/telemetry/test_roadmap_stage_steps.py`

## 2. The seed fix class of each code

Kind: other. Changes: `tests/fixtures/roadmap/stage_refused_findings.json`, `src/devops_cli/roadmap/stage/stage_finding_classes.json`.

- [x] 2.1 Add the fixture of the 42 saved refused plans and write `stage_finding_classes.json` from it with `finding_classes`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_findings.py`

## 3. Documents

Kind: other. Changes: `docs/TELEMETRY.md`, `k8s/README.md`.

- [x] 3.1 Regenerate `docs/TELEMETRY.md` and describe the log fields, the histogram and the data file in `k8s/README.md`.
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).

# Tasks

## 1. A refused reply logs the subject of each finding

Kind: behavior. Changes: `src/devops_cli/roadmap/round_log.py`, `src/devops_cli/roadmap/stage/stage_findings.py`, `tests/roadmap/stage/test_roadmap_stage_round_log.py`.

- [x] 1.1 Write the failing tests: a failed item logs the path of the finding of its last refused reply, trace findings log their paths, a pass after a return logs the findings of the last refused reply, no return logs no finding, a subject longer than 200 characters is cut, a secret in a subject is masked before the cut, a tool and a command are subjects and a check finding has `subject=none`, and a reply logs at most 20 findings.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_round_log.py`
- [x] 1.2 Add `finding_subject` to `stage_findings.py` and log one `stage gate refused finding:` line for each finding in `log_gate_returns`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_round_log.py tests/roadmap/stage/test_roadmap_stage_findings.py tests/roadmap/stage/test_roadmap_stage_gate_extension.py tests/roadmap/stage/test_roadmap_stage_plan_record.py`

## 2. Documents

Kind: other. Changes: `docs/CLUSTER.md`.

- [x] 2.1 Describe the `stage gate refused finding:` line and its subject in `docs/CLUSTER.md`.
  - Verification: `$ uv run devops ci docs`

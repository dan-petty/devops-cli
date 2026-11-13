# Proposal: #5433

## Why

Issue #5433: when the checks refuse a stage plan, the Service logs only the counts of the gates and the codes of the last refused reply (`log_gate_returns` in `src/devops_cli/roadmap/round_log.py`, #4846). On 2026-11-13 (v0.129.0) item #1976 failed with `codes=stage_problem_trace_path:10` and `stuck=7`. No log names the 10 paths, so nobody can tell if the planner claimed reads that it did not make, or if the trace gate refused true reads (the false positives of #4590). Stage is the roadmap job with the lowest success (1 of 4 in 6 hours), and `plan_defect` is its top failure class.

## What Changes

- After the unchanged `stage gate returns:` line, `log_gate_returns` logs one `stage gate refused finding:` line for each of the first 20 findings of the last refused reply: the repository, the item, the returns, the result, the place of the finding and the count of all findings (`finding=<place>/<count>`), the gate, the code and the subject.
- The subject is the path, the tool or the command that the message of the finding names: the field `path`, `tool` or `command` of its `MESSAGES.roadmap` template, in that order (`finding_subject` in `src/devops_cli/roadmap/stage/stage_findings.py`). `redact_text` (the mask of `mask_secrets`) masks it, the line keeps its first 200 characters, and the line writes it as a JSON string. A finding with no such field logs `subject=none`.
- No plan text, no finding text and no model text goes into the log, only the subject that the gate names.
- The line is an observable log line, so the change has a spec delta in `roadmap-stage-findings`.

## Capabilities

- `roadmap-stage-findings` (modified): a refused reply logs the gate, the code and the subject of each finding.

## Impact

- `src/devops_cli/roadmap/round_log.py`, `src/devops_cli/roadmap/stage/stage_findings.py`, `docs/CLUSTER.md`.
- Tests: `tests/roadmap/stage/test_roadmap_stage_round_log.py`.
- The counts line `stage gate returns:` does not change, so the queries of the shepherd keep their matches. A refused item adds at most 20 log lines.
- No setting, gate, prompt, metric or manifest changes. The stage job runs in the Service image, so the new lines come to Loki only after a release and a new Service image.

## Feasibility

- On `origin/main` (87e813d5b), `log_gate_returns` logs `_tally` of `f.gate` and `f.code` only. `stage.py` calls it at the end of each reply loop with the findings of the last refused reply (`self._last_findings()`), both when the reply passes and when it stays refused.
- `StageFinding` has `gate`, `code`, `path` and `text`. `stage_finding` fills `path` from the `{path}` field of the template that the text matches. The trace gate writes `stage_problem_trace_path` (field `path`) and `stage_problem_trace_tool` (field `tool`).
- `string.Formatter.parse` over the `stage_problem_` templates of `MESSAGES.roadmap` gives 28 templates with a `path` field, 13 with a `command` field and 1 with a `tool` field. So the template of a code gives the subject field, and the compiled pattern of `_templates()` gives its value.
- `mask_secrets` gives `docs/<masked-github-token>.md` for a path that holds a `ghp_` token, and it keeps a plain path the same.
- The new tests fail on the base: no `stage gate refused finding:` line exists (8 failed, 2 passed).

## Existing Tool Considered

- The standard `logging` module, `json.dumps` for the quoted value and `redact_text`, the mask of `mask_secrets` (`src/devops_cli/security/sanitizer.py`), which the project already uses. No new library.
- Cost: about 0.2M tokens and one hour to build, as the issue estimates.

# Proposal

## Why

A staging plan can add a field to `StageProposal` and forget the matching reply-key bullet in `src/devops_cli/ai/tasks/roadmap_stage_change.md`. The prompt test then fails during implementation, after the plan is merged. The stage job has no check for the missing prompt update, so the defect is found late and costs a fix step (#3328).

## What Changes

- Add the defect type `prompt_key_missing` and the gate name `prompt_keys` to the golden set models.
- Add the gate `prompt_keys` to `GATES` in `src/devops_cli/roadmap/stage/stage_eval_gates.py`: a plan that adds a field to `StageProposal` must change `src/devops_cli/ai/tasks/roadmap_stage_change.md` and name the new reply key and its rule.
- Add the message that names the prompt file and the missing reply key.
- Run the gate on every plan of the stage job, so a plan with the defect returns to the model.
- Add a recorded case with the defect, so the replay reports it as caught by the new gate.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A plan that adds a StageProposal field names the reply key of the prompt
- `roadmap-stage-eval`: The replay reports a plan that leaves out the prompt reply key

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/TESTING.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`, `tests/fixtures/roadmap_eval/stage/3328-missing-prompt-key/case.json`, `tests/fixtures/roadmap_eval/stage/3328-missing-prompt-key/issue.txt`, `tests/fixtures/roadmap_eval/stage/3328-missing-prompt-key/plan.json`, `tests/fixtures/roadmap_eval/stage/3328-missing-prompt-key/facts.json`

## Feasibility

- `read_file` of `src/devops_cli/roadmap/stage/stage_eval_gates.py` shows the gate set: `Gate(GateName.PATHS, "#3010", DefectType.MISSING_PATH, _path_gate)`, `Gate(GateName.KIND, "#3005", DefectType.CONTRIVED_TEST, _kind_gate)`, `Gate(GateName.CRITERIA, "#3019", DefectType.CRITERION_DROPPED, _criteria_gate)` and `Gate(GateName.CONTENT, "#3200", DefectType.OTHER, _content_gate)`, so a new gate joins that tuple.
- `read_file` of `src/devops_cli/roadmap/stage/stage_eval_cases.py` shows `class DefectType(StrEnum)` with `MISSING_PATH`, `FALSE_PREMISE`, `SPEC_DELTA_WRONG`, `VERIFY_FORM`, `TASK_ORDER`, `CRITERION_DROPPED`, `IGNORES_EXISTING_CODE`, `CONTRIVED_TEST` and `OTHER`, and `class GateName(StrEnum)` with `PATHS`, `KIND`, `CRITERIA`, `CONTENT`, `PENDING` and `NONE`.
- `read_file` of `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` shows the test that the issue names: `def test_the_top_level_keys_of_the_reply_are_the_fields_of_the_proposal() -> None:` with `bullets = re.findall(r"^- `(\w+)`:", _reply_section(_PROMPT), flags=re.MULTILINE)` and `assert sorted(bullets) == sorted(StageProposal.model_json_schema()["properties"])`.
- The probes report `The path `src/devops_cli/roadmap/stage/stage_eval_gates.py` is a file of the staging commit.` and `The path `src/devops_cli/ai/tasks/roadmap_stage_change.md` is a file of the staging commit.`, so both files that the gate reads exist.
- `read_file` of `src/devops_cli/roadmap/stage/stage_specs.py` shows that the other file that the issue names exists, and that it reads the base specs under `openspec/specs/`, a separate concern. The gate goes in `stage_eval_gates.py`, because that file holds the gate set `GATES` and the gate functions.
- The first checks against the real system: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, then `uv run devops roadmap eval stage --replay`, then `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

## Existing Tool Considered

No open, maintained tool or library covers a gate over the task groups of this project's own staging plan. The change builds its own code. The written cost is about 6,000 output tokens to build, keep and fix it, and about 2 hours of elapsed time. It deletes no internal code.

# Proposal

## Why

The plan check in `_plan_texts` refuses a placeholder in `why`, `existing_tool`, `feasibility`, the decisions and the tasks, but it skips `pull_request_body` and each line of `what_changes`. A plan with `pull_request_body="placeholder"` or `what_changes=["placeholder"]` passes `check_proposal` and reaches the pull request as a stand-in text. #3394 closes that gap.

## What Changes

- `_plan_texts` in `src/devops_cli/roadmap/stage_change.py` yields `pull_request_body` and each line of `what_changes` with the field name that the problem message names, under the rules of `PLAN_FIELD_MIN_CHARS` and `is_placeholder`.
- `tests/roadmap/test_roadmap_stage_content.py` refuses a valid plan with `pull_request_body="placeholder"`, refuses a valid plan with `what_changes=["placeholder"]`, refuses a body and a What Changes line below the least length, and accepts a valid body and valid What Changes lines.
- `src/devops_cli/ai/tasks/roadmap_stage_change.md` names `pull_request_body` and each `what_changes` line in its Texts rule beside the other checked texts, and `tests/roadmap/test_roadmap_stage_prompt_rules.py` asserts that the Texts rule names both fields.
- The `roadmap-stage/plan-text` spec modifies the requirement `A plan text is no placeholder` so that it names the two fields, with the same least length, the same placeholder rule and every scenario that it holds today.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/plan-text`: A plan text is no placeholder

## Impact

- Code: `src/devops_cli/roadmap/stage_change.py`
- Documents: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/test_roadmap_stage_content.py`, `tests/roadmap/test_roadmap_stage_prompt_rules.py`

## Feasibility

- The probes confirm the premise: `_plan_texts` is defined at src/devops_cli/roadmap/stage_change.py:551:def _plan_texts(proposal: StageProposal) -> list[tuple[str, str]]:
- The probes confirm that both fields exist on `StageProposal`: `pull_request_body` is defined at src/devops_cli/roadmap/stage_change.py:398:pull_request_body: str = Field("", min_length=1, max_length=BODY_MAX_CHARS)` and `what_changes` is defined at src/devops_cli/roadmap/stage_change.py:400:what_changes: list[Line] = Field(default_factory=list, min_length=1)`.
- The probes confirm the test file and the prompt file of the issue: the path `tests/roadmap/test_roadmap_stage_content.py` is a file of the staging commit, and the path `src/devops_cli/ai/tasks/roadmap_stage_change.md` is a file of the staging commit.
- The probes confirm that the base spec exists: the path `openspec/specs/roadmap-stage/plan-text/spec.md` is a file of the staging commit, and it holds the requirement `A plan text is no placeholder` with its five scenarios.
- The first check runs the failing test: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py`.
- The second check runs the wider suite of the package: `uv run devops ci test tests/roadmap`.
- The third check runs the static gate: `uv run devops ci`.

## Existing Tool Considered

Pydantic holds the field types of `StageProposal`, and the project already runs it. No open, maintained tool covers this repository-specific rule, so the change extends the existing `_plan_texts` scan in `src/devops_cli/roadmap/stage_change.py` and adopts no new dependency. It deletes no internal code.

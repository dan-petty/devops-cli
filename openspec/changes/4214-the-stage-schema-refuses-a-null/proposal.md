# Proposal: #4214

## Why

The prompt `roadmap_stage_change.md` tells the planner model that `reason` of an entry of `references` is "a non-empty string when `unchanged` is true, else null" (added by #4166). The class `StageReference` types `reason` as a string with the default `""`. A reply that follows the prompt sends `reason: null` and fails with `string_type`. A live run on item #3576 failed three entries this way, and the job ended the item with `StructuredOutputValidationError`. The prompt and the schema must agree, and a test must fail when they drift apart.

## What Changes

- `StageReference.reason` in `src/devops_cli/roadmap/stage/stage_change.py` accepts `null` and defaults to `null`. The check that an `unchanged` reference has a reason still refuses a null or blank reason. The one place that reads `ref.reason` (the design file) reads a null reason as an empty string.
- `tests/roadmap/stage/test_roadmap_stage_content.py` validates a plan whose reference has `unchanged: false` and `reason: null`, and refuses an unchanged reference with a null reason.
- `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` reads the value that the `references` key of the prompt gives to `reason` when `unchanged` is false, builds a reply from it and validates the reply with `StageProposal`. The prompt keeps its words.
- The `roadmap-stage` spec gains one requirement, because a reply that the schema accepts or refuses is an observable behavior of the stage job.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: adds the requirement `A reference reason may be null`.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
- No new setting. `_Reply` forbids extra keys, so no ConfigMap changes.

## Feasibility

- Line 53 of `src/devops_cli/ai/tasks/roadmap_stage_change.md` reads: "`reason` is a non-empty string when `unchanged` is true, else null."
- `StageReference` in `src/devops_cli/roadmap/stage/stage_change.py` declares `reason: Line = ""`, and `Line` is `str`.
- Command output on origin/main: `StageReference.model_json_schema()["properties"]["reason"]` shows a string type with the default `""`, and `StageReference.model_validate({"path": "src/a.py", "kind": "import", "unchanged": False, "reason": None})` raises `string_type` on `reason`.
- The live run of 2026-11-09 for item #3576 printed `loc=('references', 0, 'reason') type=string_type input=None`.
- The first check runs the new tests, which fail on origin/main: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.
- The second check runs the wider suite of the package: `uv run devops ci test tests/roadmap`.

## Existing Tool Considered

Pydantic already validates the reply: the type `Line | None` states the null in the schema that pydantic-ai sends to the model, so the model sees the same rule as the prompt. No new library or helper is needed, and the change deletes no internal code. The choice between the two fixes is in the design.

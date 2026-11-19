# Proposal: #6319

## Why

A schema limit of the plan reply that is not a plan defect fails a stage item with the class `parser` (#6319). The schema of `StageProposal` refuses a `pull_request_body` over 800 characters, and the model keeps that text long after its returns (#3915, #4012). The schema also refuses `security: null`, which the model writes for a field whose default is the empty text (#4129). The owner rule of 2026-11-17 forbids a hard character cap that fails a job.

## What Changes

- The reply schema holds no maximum length on `pull_request_body`. The stage constant `BODY_MAX_CHARS` of `stage_change.py` goes, because no code reads it after the change. The stage prompt keeps its aim of 800 characters, and a test holds that a body of that length fits the plan form with the longest issue number and slug.
- `pull_form.plan_body_room` gives the characters that the `Plans` line and the `Change:` line leave for the text in the 1000 characters of the plan form. `build_plan_body` builds its lines with the same helper.
- When the text of the body is longer than its room, the stage job asks the model once for a shorter text. It uses the reply `BodyReply` and the prompt of the pull body rewrite (`pull_retry.BODY_TASK`), and builds the draft body from the shorter text. The proposal and the kept plan keep the full text. A shorter text that the plan form still refuses goes back to the planner as a refused body, as before.
- A null `security` and a null `kind` of a reference read as their default empty text (`OptionalLine`, a Pydantic `BeforeValidator`). A value of another type still breaks the schema and goes back to the model once with its field.
- `pull_request_body` of `stage_change.py` takes the text of the body, not the proposal, so the job can build a body from the shorter text.
- The change carries a spec delta in `roadmap-stage/replies`, because the reply schema and the requests of the stage job are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/replies`: a long plan body gets a shorter text from one model turn, and a null optional text reads as its default.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/roadmap/pull_retry.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/stage/test_roadmap_stage_plan_check.py`, `tests/roadmap/test_roadmap_pull_form.py`
- The stage planner prompt `roadmap_stage_change.md` does not change, so the change needs no live stage eval.

## Feasibility

- `git grep` on `origin/main` at `6ff83d43f` shows `pull_request_body: str = Field(min_length=1, max_length=BODY_MAX_CHARS)` at `src/devops_cli/roadmap/stage/stage_change.py:699` with `BODY_MAX_CHARS: Final[int] = 800` at line 130, and `security: Line = ""` at line 714. `Line` is a `str` with no step for `None`, so Pydantic refuses `null` with `string_type`.
- `Stage._plan_body` in `src/devops_cli/roadmap/stage/stage.py` builds the body with `build_plan_body`, which refuses a body over `BODY_MAX_CHARS` (1000) of `pull_form.py`. With no schema cap, a long text reaches that check and goes back to the planner, which plans the whole item again. One plan run of #6319 used about 16.8 M tokens in 79 minutes, so a short rewrite turn is much cheaper than a return to the planner.
- `src/devops_cli/roadmap/pull_retry.py` already holds `BodyReply` and the prompt `roadmap_implement_body.md`, which rewrites a refused pull request body to fit its limit and keep its facts. The implement job uses them through `retried_body`.
- `chat_structured` of the stage sends a reply that breaks the schema back once (`_REPLY_RETURNS`), and the toolbox passes the same count as `output_retries`. So a wrong-typed `security` already returns once; the change keeps that path.
- `StageToolbox.chat_structured` sends a schema that is not a plan or a review to its inner client, so the rewrite turn uses no tool and no plan budget.

## Existing Tool Considered

- Pydantic (https://github.com/pydantic/pydantic, MIT, maintained), already a dependency, covers the schema part: a field with no `max_length` and a `BeforeValidator` that maps `None` to the default. The alternatives check of the issue gives the verdict `in-use`.
- The pull body rewrite of `src/devops_cli/roadmap/pull_retry.py` (`BodyReply`, `roadmap_implement_body.md`) covers the shorter text. The stage uses it and writes no new prompt.
- The change builds only the room helper of the plan form and the call of the rewrite in the stage: about 20 k tokens and 1 hour to build, keep and fix.
- The change deletes the stage constant `BODY_MAX_CHARS` and the schema cap that read it.

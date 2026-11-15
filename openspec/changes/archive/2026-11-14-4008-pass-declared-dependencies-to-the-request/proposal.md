# Proposal

## Why

The stage prompt tells the model to write a `dependencies` entry for each issue that must come first, but the request holds no structured list of the issues that the body declares. The body is also cut to a token limit, so a long Dependencies section can be out of the request. The model must find the declarations in the text, and it often omits one (#4008).

## What Changes

- Add `issue_dependencies` to `StageRequest`: one entry for each issue of the Dependencies section of the body, with `number` and, when the store holds the issue, `title`.
- Build the entries in `stage.py` with `body_dependencies`, and look the titles up in the store of the round, so the plan makes no GitHub request.
- Omit the key when the body declares no dependency, as `overlaps` and `metric_senders` do.
- Tell the model in `roadmap_stage_change.md` to read `issue_dependencies` and to write one `dependencies` entry for each as `#<number>: <reason>`.
- Add the request test in `tests/roadmap/stage/test_roadmap_stage_plan.py` and the prompt rule in `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/context`: the request lists the declared issue dependencies.

## Impact

- Code: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_request.py`
- Prompt: `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/stage/test_roadmap_stage_request.py`

## Feasibility

- Read on `origin/main`, 2026-11-14. `src/devops_cli/roadmap/refine/refine.py:1159:def body_dependencies(` reads the declarations, and `src/devops_cli/roadmap/stage/stage.py:2001:def _request(` builds the request.
- `src/devops_cli/roadmap/stage/stage_request.py:30:class StageRequest(` holds `overlaps` and `metric_senders` as the pattern of an optional key.
- `src/devops_cli/roadmap/stores/store.py:1032:def item(` reads the title, and the round reads that store already.
- `uv run pytest tests/roadmap/stage` passes after the change.

## Existing Tool Considered

No open, maintained tool passes the dependencies of an internal prompt request. The change adds one field and one prompt rule: about 2,000 tokens to build and 200 a quarter to keep.

## Dependencies

None.

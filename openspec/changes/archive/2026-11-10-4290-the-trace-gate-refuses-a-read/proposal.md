# Proposal: #4290

## Why

The trace gate of the stage job refuses a Feasibility sentence that is true (#4290). It compares a whole code span with the paths that the run read. The stage prompt asks for `path:line:text` and `path:def name`, and the span of such a citation is never a read path, so the gate refuses every citation of a file that the run did read. It also takes the word `read` in a quoted line of code as a claim of a read. In the stage job logs of 2026-11-09, 14 of 25 refusals "was read, but the run did not read it" from 15:00Z on name a citation span.

## What Changes

- Judge the path of a `path:line:text` or `path:def name` span in `_uncalled_path` of `src/devops_cli/roadmap/stage/stage_change.py`, remove a leading `./`, and accept a claim that names a file by its name or by the end of its path when the run read a path that ends with it.
- Read the words of a sentence outside the code spans, except the name of a toolbox tool, so the word `read` in a quoted line is no claim.
- Name the path, and not the whole citation, in the refusal.
- The change carries a spec delta because it changes which Feasibility claims the stage job refuses.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: The trace gate reads the path of a citation and the words outside the code spans

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_trace_spans.py`

## Feasibility

- The cause is in the code: `_uncalled_path` in `src/devops_cli/roadmap/stage/stage_change.py` tested `span not in trace.paths`, and `TraceFacts.of` in `src/devops_cli/roadmap/agent_run.py` holds the bare values of the `path`, `directory` and `paths` arguments.
- The stage job logs of the last 7 days (Loki, `service_name=roadmap-service`) hold the refusals. Word for word, from #3662: "The Feasibility section states that `src/devops_cli/roadmap/pull_form.py:283:def plan_body_problems(body: str, issue: int) -> list[str]:` was read, but the run did not read it." From #4004: "The Feasibility section states that `src/devops_cli/config/constants.py:308: (("ai", "read"), 60.0, True, False),` was read, but the run did not read it."
- A live stage run on #3599 with the live stage model on 2026-11-09 refused a plan for the same reason: "The Feasibility section states that `src/devops_cli/ai/task_loader.py:def load_task_prompt` was read, but the run did not read it."
- First check against the real system: `uv run devops roadmap eval stage --replay`, which runs the recorded plans through the gates and must keep its verdict on every case.
- Second check: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_trace_spans.py tests/roadmap/stage/test_roadmap_stage_content.py`.

## Existing Tool Considered

No library judges a sentence of a plan. The change reuses `_CITED_PATH` and `_CODE_SPAN` of the same module and adds no parser; the cost is about 25k tokens to build, 3k tokens to keep and 1 hour. The change deletes no internal code.

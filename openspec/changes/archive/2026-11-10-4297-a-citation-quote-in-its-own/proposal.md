# Proposal: #4297

## Why

The citation check of the stage job refuses a line citation that follows the stage prompt (#4297). The prompt in `src/devops_cli/ai/tasks/roadmap_stage_change.md` says: "write the citation as `path:line:text`, with the text of that line in a code span". A plan can write `path:line:` and then the text in a code span of its own. `_LINE_CITATION` in `src/devops_cli/roadmap/stage/stage_change.py` reads the text up to the next backtick, so for this form the text is a space and the check says "cites `src/x.py` with fewer than 3 characters of the line". The stage job logs of 2026-11-09 hold this sentence for four items (#3406, #3462, #3532 and #3612), seven times for #3532 alone.

## What Changes

- Take the text of a line citation from the code span that follows `path:line:` when the text up to the next backtick is empty. The closing backtick of the citation and white space may stand between them.
- The change carries a spec delta because it changes which plans the stage job refuses.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A line citation may hold its text in the code span that follows it

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_citation_quote.py`

## Feasibility

- The cause is in the code: `_line_citation_problem` in `src/devops_cli/roadmap/stage/stage_change.py` squashes the text of the match, and the pattern `_LINE_CITATION` ends that text at the first backtick.
- The stage job logs of the last 24 hours (Loki, `service_name=roadmap-service`) hold the refusals. Word for word, from #3406: "The feasibility of the plan cites `src/devops_cli/roadmap/stage/stage_probe.py` with fewer than 3 characters of the line. Quote at least 3 characters of the line, or cite a symbol as `path:def name` or `path:class name`." The log keeps the problem and not the reply, so the form of the reply is read from the pattern and the prompt, and the live check after the change tests it.
- First check against the real system: `uv run devops roadmap eval stage --replay`, which must keep its verdict on every case.
- Second check: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_citation_quote.py tests/roadmap/stage/test_roadmap_stage_content.py`.

## Existing Tool Considered

No library reads the citation form of this project. The change adds one pattern next to `_LINE_CITATION`; the cost is about 15k tokens to build, 2k tokens to keep and 45 minutes. The change deletes no internal code.

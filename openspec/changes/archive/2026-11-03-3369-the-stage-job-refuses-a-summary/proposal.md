# Proposal

## Why

The stage job decides whether an item may be planned, and its title check does not look at the length of the summary (#3369). The implement job then cuts the summary to 60 UTF-16 code units and adds `...`, so the delivery title differs from the issue title and ends in a form that `devops pr create` refuses. The cost is paid after the plan run has already spent its model calls.

## What Changes

- `_Judge._title` in `src/devops_cli/roadmap/stage.py` refuses a title whose summary is longer than `SUMMARY_MAX_CHARS` UTF-16 units, counted by `summary_length` from `src/devops_cli/roadmap/pull_form.py`.
- A new message `stage_left_title_long` in `src/devops_cli/lang/en/messages.py` names the current length and the limit.
- New cases in `tests/roadmap/test_roadmap_stage_title.py` cover a summary of 61 units, which is refused, a summary of 60 units, which passes the length check, and a title with no type, which keeps its reason.
- The change fits one pull request.

`delivery_title` in `src/devops_cli/roadmap/stage_change.py` no longer cuts an overlong summary: #3200 removed that cut, so the delivery title keeps the whole summary and the pull-request form judges it. The stage gate now refuses the item before the plan run, which is where the cost is paid. No cut remains as a fallback, and no test asserts a cut.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A title whose summary is over the limit is refused

## Impact

- Code: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/test_roadmap_stage_title.py`

## Feasibility

- The context shows `def _title(self, item: Item) -> str | None:` in `src/devops_cli/roadmap/stage.py`, the method the issue names, so the check has a place to go.
- The context shows `SUMMARY_MAX_CHARS: Final[int] = 60` and `def summary_length(text: str) -> int` in `src/devops_cli/roadmap/pull_form.py`, with the count `len(text) + sum(ord(char) > 0xFFFF for char in text)`, so the count is in UTF-16 code units.
- The context lists `delivery_title` in `src/devops_cli/roadmap/stage_change.py` and its caller in `src/devops_cli/roadmap/implement_run.py`, and lists `tests/roadmap/test_roadmap_stage_title.py` as a test of `delivery_title` and of `SUMMARY_MAX_CHARS`.
- `probes` reports that `tests/roadmap/test_roadmap_stage.py` is no file of the staging commit and that no commit deleted or renamed it, so the new cases go in `tests/roadmap/test_roadmap_stage_title.py`.
- The first checks against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_title.py`, then `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py`, then `uv run devops openspec check`.

## Existing Tool Considered

No open, maintained tool or library covers this check, because it is an internal rule of the roadmap stage gate. The change builds about 10 lines and two tests itself, which costs about 2,000 tokens and 30 minutes to build, keep and fix. It deletes no internal code: the cut in `delivery_title` stays as the fallback.

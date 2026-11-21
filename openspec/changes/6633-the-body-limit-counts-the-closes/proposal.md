# Proposal

## Why

The delivery body limit has two meanings in the code and in the text that a person reads. `CONTRIBUTING.md:181:in at most 1,000 characters before the trailers` and the message field `form_body_long` measure the text above `Closes`, and `pull_form` measures the `Closes` line, the empty lines and the `Change:` line as well, about 120 characters of a typical change folder. A body of 990 characters above `Closes` is therefore refused at ready, and the merges of #6625 and #6629 waited on that refusal. Issue #6633 asks for one meaning in the code, the message and the document, for the plan body, and for the plan check.

## What Changes

- `_text_problems` measures the text above the trailer line with its trailing blank lines removed, so `body_problems` counts the text above `Closes` and `plan_body_problems` counts the text above `Plans` only.
- `open_body_problems` measures the text above `Closes` instead of the text up to the `Change:` line, so the open step and the ready check agree.
- `measured_body_text` holds the one measure of the text above a trailer line, and `open_body_problems` and the plan check read it.
- `form_body_long` names the line that it measured through a `{line}` placeholder, and `plan_check_body_long` names the text above `Plans`.
- `plan_body_room` gives the whole limit as the room of a plan text, so a plan text of 1,000 characters builds.
- `_why` of the implement job sets the room of the why to the whole limit, so a why of 990 characters is kept instead of giving way to the title of the item.
- `title_body_problems` of the plan check measures the text above `Plans`, not the whole body.
- `CONTRIBUTING.md` and `docs/roadmap/plan-check.md` state the part that the 1,000-character limit measures.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pull-request-form`: The plan body limit measures the text above Plans, The body ends with Closes and the Change line
- `roadmap-plan-check`: Plan-check checks the body of the pull request

## Impact

- Code: `src/devops_cli/roadmap/pull_form.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/plan_check.py`
- Documents: `CONTRIBUTING.md`, `docs/roadmap/plan-check.md`
- Tests: `tests/roadmap/test_roadmap_pull_form.py`, `tests/roadmap/steps/test_roadmap_step_open.py`, `tests/core/test_roadmap_implement_planned_run.py`, `tests/roadmap/test_roadmap_plan_check.py`

## Feasibility

- The probes confirm the cited files: "The path `src/devops_cli/roadmap/pull_form.py` is a file of the staging commit." and "The path `src/devops_cli/lang/en/messages.py` is a file of the staging commit." and "The path `CONTRIBUTING.md` is a file of the staging commit." Those two modules hold `BODY_MAX_CHARS: Final[int] = CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS` and `form_body_long: str = (`.
- The probe for the third file names the real path: "The path `plan_check.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/plan_check.py`. No commit in the history deleted or renamed it." That module holds `measured = len(body)`.
- The premise holds in the staged code: `body_problems` passes the lines up to and including the `Change:` line as the measured text, `src/devops_cli/roadmap/pull_form.py:316:"\n".join(lines[:closes_at]), "\n".join(lines[: change_at + 1])`, and `src/devops_cli/roadmap/pull_form.py:380:if len(measured) > BODY_MAX_CHARS:` refuses it.
- The plan check counts the whole body: `src/devops_cli/roadmap/plan_check.py:278:measured = len(body)` and `src/devops_cli/roadmap/plan_check.py:279:if measured > BODY_MAX_CHARS:` compare the whole text with the limit.
- The bound is staged as `src/devops_cli/config/constants.py:3721:CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS: Final[int] = 1000`, and `src/devops_cli/roadmap/pull_form.py:57:BODY_MAX_CHARS: Final[int] = CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS` holds it.
- The delivery message gives the other meaning: `src/devops_cli/lang/en/messages.py:1700:The body has {length} characters before its trailers.` The field at `src/devops_cli/lang/en/messages.py:1699:form_body_long: str = (` serves both forms, and `src/devops_cli/lang/en/messages.py:5658:plan_check_body_long: str = "The body has {length} characters, and the limit is {limit}."` names no part at all.
- The document gives it too: `CONTRIBUTING.md:181:in at most 1,000 characters before the trailers`.
- Two further places subtract the trailer lines from the same bound: `src/devops_cli/roadmap/pull_form.py:452:return BODY_MAX_CHARS - len(_plan_lines(issue, change))` and `src/devops_cli/roadmap/implement/implement_run.py:1394:room = BODY_MAX_CHARS - len(`.
- The plan check's document states the whole-body measure: `docs/roadmap/plan-check.md:77:The body: at most`.
- The tests that hold the old measure are `tests/roadmap/test_roadmap_pull_form.py:252:def test_a_body_over_the_limit_before_its_trailers_is_refused() -> None:`, `tests/roadmap/test_roadmap_pull_form.py:451:def test_a_plan_text_over_the_limit_is_refused_and_not_cut() -> None:` and `tests/roadmap/test_roadmap_pull_form.py:def test_the_room_of_a_plan_text_is_the_text_that_the_plan_form_takes`.
- The issue names `body_form_problems`, and this run did not search the staged tree for that name (not checked). The plan changes the two functions that hold the measure: `src/devops_cli/roadmap/pull_form.py:243:def open_body_problems(body: str, *, issue: int | None, plan: bool) -> list[str]:` and `src/devops_cli/roadmap/pull_form.py:364:def _text_problems(text: str, measured: str, *, short_message: str | None = None) -> list[str]:`.
- No function that the plan calls needs a checkout, a client or a network: `open_body_problems`, `body_problems`, `plan_body_problems`, `_text_problems` and `measured_body_text` take a string.
- No command and no verify program is new: the verifies are `uv run devops ci test tests/roadmap/test_roadmap_pull_form.py` and `uv run devops ci docs`, which start `pytest` and `devops`, both tools of the runner image, so none is `NOT_IN_RUNNER`; the pod keeps its read-only root, its non-root user and its dropped capabilities.
- GitHub was not read in this run, because `read_issue` and `find_issues` were not called: the plan states no fact of #2585, #6625, #6629 or #6450, and the three overlaps share the messages file, whose `form_body_long: str = (` this change edits.
- No feasibility line names a module in a bare code span: each module appears only in a `path:line:text` or a `path:def name` span that holds its staged line.
- The input holds no `rejected_plan`, and the first checks of the implementation are `uv run devops ci test tests/roadmap/test_roadmap_pull_form.py` on the new tests, which must fail before the edit, and `uv run devops pr check-readiness` on a body of 1,000 characters above `Closes`.

## Existing Tool Considered

The alternatives check of 2026-11-21 gives the verdict none, and no open tool implements this repository's 1,000-character delivery body rule or the split of the body text from its `Closes` and `Change:` lines, so the fix edits the existing checker in `src/devops_cli/roadmap/pull_form.py` and builds no new component.

## Dependencies

- PR #6693 shares `src/devops_cli/lang/en/messages.py`, where this change edits `form_body_long` and `plan_check_body_long`; whichever pull request merges first, the other rebases on it.
- PR #6695 shares `src/devops_cli/lang/en/messages.py`, where this change edits `form_body_long` and `plan_check_body_long`; whichever pull request merges first, the other rebases on it.
- PR #6699 shares `src/devops_cli/lang/en/messages.py`, where this change edits `form_body_long` and `plan_check_body_long`; whichever pull request merges first, the other rebases on it.

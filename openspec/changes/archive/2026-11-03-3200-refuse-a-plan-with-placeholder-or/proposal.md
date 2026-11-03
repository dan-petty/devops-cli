# Proposal

## Why

The stage job accepts plan text that is a placeholder or cut (#3200). A plan with `x` in `why`, `todo` as the existing tool, a `true` verify command or a summary cut with `...` passes every gate and opens a pull request. A person then spends a review round on a plan that no implement job can use.

## What Changes

- `check_proposal` runs a new content check that refuses a text field under a named bound, or a field whose whole text is a placeholder word. It covers `why`, `existing_tool`, each line of `feasibility`, each decision and each task text.
- The content check uses the `is_placeholder` function of `src/devops_cli/roadmap/pull_form.py` and adds no second placeholder list.
- `check_proposal` refuses a `feasibility` list that quotes no line of `probes` when `probes` is not empty.
- `StageProposal` gains `builds_own`, and the content check requires a token count and a time in `existing_tool` when it is true.
- `lang/en/messages.py` holds one message for each refusal, and each message names its field.
- `StageProposal.summary` already has the bound of the title room, 47 characters for the longest issue number (#3249; the issue text says 40, which is stale). The schema now also refuses a summary that ends with `...`. `delivery_title` uses the full summary and adds no `...`: `staging_title` already does.
- `stage.py` passes the probe lines of the item to `check_proposal`, because the job makes the only call that has them.
- `stage_eval_gates.py` gains `GateName.CONTENT` and a gate that catches `DefectType.OTHER`.
- The golden set gains the recorded placeholder plan of #3167 as one case with a defect of type `other` (gate `content`) and a defect of type `verify_form` (gate `paths`), and the case-count assertions of the eval test follow.
- The change alters what the stage job accepts, so it carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A plan text is no placeholder, Feasibility quotes a probe line, Existing tool holds a build cost, The summary of a plan is not cut, A title holds the full summary, The replay judges a placeholder plan

## Impact

- Code: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Tests: `tests/roadmap/test_roadmap_stage_content.py`, `tests/roadmap/test_roadmap_stage_title.py`, `tests/roadmap/test_roadmap_stage_eval_gates.py`, `tests/fixtures/roadmap_eval/stage/3167-a-comment-by-a-person-on/`, `tests/roadmap/test_roadmap_stage_eval_cases.py`

## Feasibility

- `read_file` on `src/devops_cli/roadmap/stage_change.py` showed `check_proposal` with no content check: it extends `_delta_problems`, `form_problems`, `path_problems` and `criterion_problems` only. The premise of the issue holds.
- `read_file` on `src/devops_cli/roadmap/stage_change.py` showed that `staging_title` no longer cuts (#3249) and that `STAGE_SUMMARY_MAX_CHARS` already bounds the summary. The cut title was real for `staging_title` until #3249 and is still real for `delivery_title`.
- `read_file` on `src/devops_cli/roadmap/stage_change.py` showed `def delivery_title(issue_title: str, declared: Collection[str]) -> str:` with `shortened = textwrap.shorten(safe_text(summary), SUMMARY_MAX_CHARS, placeholder=_ELLIPSIS)`.
- `read_file` on `src/devops_cli/roadmap/stage_eval_gates.py` showed `GATES: Final[tuple[Gate, ...]] = (` with the gates `PATHS`, `KIND` and `CRITERIA`, and `PENDING_GATES: Final[Mapping[DefectType, str]] = {}`. No gate catches `DefectType.OTHER` today.
- `read_file` on `src/devops_cli/roadmap/pull_form.py` showed `def is_placeholder(text: str) -> bool:`, so the placeholder rule of the content gate reuses that function and adds no second word list.
- `read_file` on `tests/roadmap/test_roadmap_stage_eval_cases.py` showed that it asserts the case count and the evaluated pull numbers, so two new cases change those assertions and the change updates them.
- `read_file` on `AGENTS.md` showed rule 3: `**Use an open tool before you build.** Name the tool or library that covers the need. To build instead, write the cost in the issue or pull request: tokens to build, keep and fix it, and elapsed time.` The cost rule is the project rule that the gate enforces.
- First check against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_content.py` runs the new content tests.
- First check against the real system: `uv run devops ci test tests/roadmap/test_roadmap_stage_eval_gates.py` replays the golden set through the new content gate.
- First check against the real system: `uv run devops openspec check` validates the change folder against the base specs.
- `read_file` on `src/devops_cli/roadmap/stage.py` showed that `_settle` calls `check_proposal` with no probe lines, and `src/devops_cli/roadmap/pull_form.py` showed `SUMMARY_MAX_CHARS = 60`, while `src/devops_cli/ai/tasks/roadmap_stage_change.md` states a limit of 47 characters. The issue text of 40 is stale, so the change uses 47.

## Existing Tool Considered

Pydantic is an open, maintained library. It enforces a minimum length and a pattern on one field, and it cannot check that `feasibility` quotes a probe line or that `existing_tool` holds a cost. The project keeps these cross-field gates in `src/devops_cli/roadmap/stage_change.py` (#3013, #3017, #3019), so this change extends them. Cost to build instead: about 80k tokens and 4 hours. Cost to keep: four small functions and their tests, and the fix cost of one rule set that the job and the replay share. This change deletes no internal code: `textwrap.shorten` is a library call, and the change removes its two call sites.

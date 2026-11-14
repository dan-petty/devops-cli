# Proposal

## Why

On 2026-11-13 the fix-plan step of the roadmap ended plan pull request #5449 as `dismissed` with two blockers and five major findings still open, and the Service marked the plan ready (#5579). The reader of the last plan comment knew one line form only, so the three findings of the stage review read as unreadable and vanished, and a finding of the type `other` never blocked whatever its severity. The step then dismissed a plan that still held open defects.

## What Changes

- Read a finding line of a plan comment in the current form and in the old form that a release before #5418 wrote, and give an old place the part that its first word names.
- Return the lines of the open findings section that neither form reads, and end such an attempt as `unreadable_findings` before any model call, with the label kept and the count `unreadable` in the result line.
- Dismiss a plan only when the review of the head and the last plan comment list no blocker or major finding.
- Hold every type that the verification pass may return in `OPEN_TYPES`, so the severity alone decides whether a finding is open and a major `other` finding blocks the plan.
- Give `JUDGE_OPEN_TYPES` an explicit literal of its four types, so the review of refine keeps the open set that its requirement names while `OPEN_TYPES` widens.
- Carry a spec delta of `roadmap-stage/fix-plan` and `roadmap-stage/verification`; the step result name, the label policy and the open set are behavior that a consumer observes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/verification`: Only a blocker or a major finding is open
- `roadmap-stage/fix-plan`: A plan comment line that the step cannot read keeps the label, An open finding of the last plan comment keeps the label, A plan comment line is read in either of its forms, The decisions of the step count only blocker and major findings

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_verify.py`, `src/devops_cli/roadmap/refine/refine_judge.py`, `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_verify.py`, `tests/roadmap/stage/test_roadmap_stage_verification.py`, `tests/roadmap/refine/test_roadmap_refine_trust.py`, `tests/roadmap/steps/test_roadmap_fix_plan_comment.py`, `tests/roadmap/steps/test_roadmap_fix_plan.py`

## Feasibility

- Probes: "The path `src/devops_cli/roadmap/steps/fix_plan.py` is a file of the staging commit." The step and its reader live there.
- Probes: "The path `stage_verify.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_verify.py`. No commit in the history deleted or renamed it." The constant that the issue cites is at that path.
- Probes: "The path `roadmap.fix_plan.mode` is no file of the staging commit. No commit in the history deleted or renamed it." `roadmap.fix_plan.mode` is a setting and no path, so that answer is expected and shows no false premise.
- `read_file` on `src/devops_cli/roadmap/steps/fix_plan.py:341:def comment_open_findings(body: str) -> tuple[Finding, ...]:` shows one reader and one line form. `src/devops_cli/roadmap/steps/fix_plan.py:356: if len(findings) < len(lines):` logs the lines it drops and keeps none of them.
- `read_file` on `src/devops_cli/roadmap/steps/fix_plan.py:193:_FINDING_LINE: Final[re.Pattern[str]] = re.compile(` shows the one form that the reader knows, and `src/devops_cli/roadmap/steps/fix_plan.py:def _finding_of` builds a `Locator` from a `PlanPart`, so an old line that names `group 3 (and group 1)` names no part and reads as None.
- The old form: `openspec/changes/archive/2026-11-13-5410-a-review-finding-must-name-a/proposal.md:47:- The real stage comments of the fixtures name places such as "specs (metric-instruments) and the rejected alternatives of group 2", "criteria (criterion 3) / group 4" and "group 2 (and the decision on service.instance.id)". No rule can read such free text as a part of the plan.`
- `read_file` on `src/devops_cli/roadmap/stage/stage_verify.py:88:OPEN_TYPES: Final[frozenset[DefectType]] = frozenset(` gives seven types, and `src/devops_cli/roadmap/stage/stage_verify.py:104:VERIFY_TYPES: Final[frozenset[DefectType]] = OPEN_TYPES | {` adds `contrived_test` and `other`. The pass names nine types, and `other` is in none of the seven.
- The staged value of each constant that the plan relies on: `OPEN_SEVERITIES` is `frozenset({Severity.BLOCKER, Severity.MAJOR})` (`src/devops_cli/roadmap/stage/stage_verify.py:102:OPEN_SEVERITIES: Final[frozenset[Severity]] = frozenset({Severity.BLOCKER, Severity.MAJOR})`), `_UNGRADED_SEVERITY` is `Severity.MAJOR` (`src/devops_cli/roadmap/steps/fix_plan.py:201:_UNGRADED_SEVERITY: Final[Severity] = Severity.MAJOR`), and `PLAN_NEEDS_FIX_LABEL` is `plan/needs-fix` (`src/devops_cli/roadmap/stage/stage_verify.py:109:PLAN_NEEDS_FIX_LABEL: Final[str] = "plan/needs-fix"`). The plan adds no bound of a constant that the staged tree defines.
- `src/devops_cli/roadmap/stage/stage_verify.py:626:if f.severity in OPEN_SEVERITIES` and `src/devops_cli/roadmap/stage/stage_verify.py:629:(f.type in types and given.contains(f.quote))` show that the severity and the type both decide today, so a major `other` finding fails the second test and becomes advice.
- The claim over the set of nine types: all nine become open by their severity and no member is removed, restricted or allowlisted. The count is nine, from `tests/roadmap/stage/test_roadmap_stage_verify.py:104: assert len(VERIFY_TYPES) == 9`: seven members of `OPEN_TYPES` plus `contrived_test` and `other`.
- The answer to the finding of the review: `src/devops_cli/roadmap/refine/refine_judge.py:43:JUDGE_OPEN_TYPES: Final[frozenset[DefectType]] = OPEN_TYPES - {` is a subtraction, so widening `OPEN_TYPES` would widen the review of refine too and refuse a bot item on a major `other` finding. Group 3 replaces it with an explicit literal of the four types, and `openspec/specs/roadmap-refine/review/spec.md:27:or a placeholder, that quotes the input and names a place of the proposal` keeps its four open types, so that capability carries no delta.
- Group 1 widens the open set of the stage job, so two existing tests that assert a major `contrived_test` finding is advice change with it: `tests/roadmap/stage/test_roadmap_stage_verify.py:test_an_open_type_with_a_quote_in_the_input_is_open` and `tests/roadmap/stage/test_roadmap_stage_verify.py:test_an_open_finding_is_a_listed_type_or_a_placeholder_with_a_quote_in_the_input`. Group 2 gives the same severity change to the two tests of `tests/roadmap/stage/test_roadmap_stage_verification.py` that assert it.
- `references` for `_FINDING_LINE` answers "files 6, lines 7": `src/devops_cli/roadmap/steps/fix_plan.py` (lines 193 and 322) and five files under `openspec/changes/archive/`. Only the first sits outside the archive, and groups 4, 5 and 6 change it.
- `src/devops_cli/roadmap/steps/fix_plan.py:def _decide` reads only `revision.before`, so the three findings of #5449 would still end `dismissed` after the reader alone changes. Group 6 adds the open findings of the comment to that rule.
- `read_issue 5449` answers that the plan pull request is closed and merged, so the defect is in the step and no open pull request holds the fix. `find_issues` answers `#5588 open chore(roadmap): re-run fix-plan on #5449 after the unreadable-findings fix`, which is the live proof after this change and needs no code here, and `#5211 open fix(roadmap): track the plan reader and fix-plan repairs`, a tracker whose children change the same module; neither is delivered first.
- Preconditions of the calls that the plan makes: `revise_plan` needs a checkout of the repository and a client of the model service, which the tests double; `run_fix_plan` needs a checkout, a GitHub client and the store; `_push` needs a checkout and a network to `origin`; `comment_open_findings`, `open_findings` and `_decide` need no checkout, no client and no network.
- not checked: the text of `docs/roadmap/stage.md` and of the verification prompt `roadmap_stage_verify.md`, so the plan changes no document.
- First checks that the implementation runs against the real system: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify.py`, `uv run devops ci test tests/roadmap/refine/test_roadmap_refine_trust.py`, `uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan_comment.py` and `uv run devops ci test tests/roadmap/steps/test_roadmap_fix_plan.py`.
- The verifies run `uv run devops ci test`, which the runner image holds with `uv` and `pytest`; no program is `NOT_IN_RUNNER` and no new program joins. A failing case is the failure class `test`, whose action is `repair`. The cases run in the pod with `readOnlyRootFilesystem: true`, `runAsNonRoot: true` and no network, and they double the process edges only.

## Existing Tool Considered

No open, maintained tool or library reads this project's plan comment line or decides which review finding keeps a plan draft: the line form and the label rule are this repository's own, and no package covers them. The change edits `src/devops_cli/roadmap/steps/fix_plan.py`, `src/devops_cli/roadmap/stage/stage_verify.py` and `src/devops_cli/roadmap/refine/refine_judge.py` and adds no dependency. Cost: about 30k tokens and 2 hours to build, keep and fix.

## Dependencies

None.

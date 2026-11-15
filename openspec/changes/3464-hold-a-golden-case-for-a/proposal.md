# Proposal

## Why

The golden set of the roadmap stage has no case for the defect that #3427 adds a rule for: a behavior group whose `verify` runs a test module that the group does not name in `test`, `changes`, `creates` or `reads`. Only the unit test of `form_problems` checks the rule, so a regression of it fails no replay (#3464).

## What Changes

- Label group 1 of `tests/fixtures/roadmap_eval/stage/2576-a-token-that-argo-cd-refuses/case.json` with one `verify_form` defect at the `paths` gate, whose message `which runs no test module of the group` is the words of the form rule.
- Add `test_the_replay_of_the_plan_of_2576_is_refused_for_its_unnamed_verify_test` to `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, which requires the new defect to be `DefectStatus.CAUGHT` and the gate problem to hold the words of the rule.
- Move the counts of `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`: `JUDGED_BASELINE` to (83, 320), the `VERIFY_FORM` row to (7, 0, 12) and the count of the defects that waited for a gate to 77.
- Move the totals of `tests/roadmap/stage/test_roadmap_stage_eval_command.py`: the share line to `83 of 320 (26%)`, the JSON `defects` to judged 83 and known 320, and the `verify_form` row to (7, 0, 12).
- Add no value to `DefectType`: `VERIFY_FORM` at the `paths` gate already judges the defect, and the issue allows no gate code.
- The change touches only paths under `tests/`, so it carries no spec delta: a golden case and its replay are test data and a test.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Tests: `tests/fixtures/roadmap_eval/stage/2576-a-token-that-argo-cd-refuses/case.json`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py`

## Feasibility

- This run read `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` lines 40 to 60 and 240 to 300, `tests/roadmap/stage/test_roadmap_stage_eval_command.py` lines 70 to 110 and `tests/fixtures/roadmap_eval/stage/2576-a-token-that-argo-cd-refuses/case.json` from line 1, and every claim below comes from a call of this run.
- The issue cites `src/devops_cli/roadmap/stage_eval_cases.py`, and the probe answers word for word: The path `src/devops_cli/roadmap/stage_eval_cases.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_eval_cases.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it. The plan names the staged path.
- The issue cites `tests/roadmap/test_roadmap_stage_eval_gates.py`, and the probe answers word for word: The path `tests/roadmap/test_roadmap_stage_eval_gates.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`. Commit bff2f14f 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it. The plan names the staged path.
- The probe for the third cited path answers word for word: The path `tests/test_argo_credentials.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/argo/test_argo_credentials.py`. No commit in the history deleted or renamed it, so the test module that group 1 of the recorded plan runs sits under `tests/argo/` and no group of that plan names it.
- `src/devops_cli/roadmap/stage/stage_form.py:def _behavior_test_run_problems` returns one problem for a `behavior` group whose `verify` runs a test module that `test`, `changes`, `creates` and `reads` name none of, and `git_log` of that file gives `65268d6f 2026-11-14 fix(roadmap): refuse a behavior verify that runs no test (#5684)` as the newest commit, so the rule is at the staged commit.
- `read_issue` of #3463 gives closed (completed) with the comment Released in v0.138.0, so the rule that refuses the recorded plan is delivered and the case can carry its defect now.
- `read_file` of `tests/fixtures/roadmap_eval/stage/2576-a-token-that-argo-cd-refuses/plan.json` lines 130 to 143 showed group 1 with `tests/fixtures/roadmap_eval/stage/2576-a-token-that-argo-cd-refuses/plan.json:143:"kind": "behavior"`, `tests/fixtures/roadmap_eval/stage/2576-a-token-that-argo-cd-refuses/plan.json:133:"reads": [],`, `tests/fixtures/roadmap_eval/stage/2576-a-token-that-argo-cd-refuses/plan.json:137:"creates": [],` and `tests/fixtures/roadmap_eval/stage/2576-a-token-that-argo-cd-refuses/plan.json:141:"verify": "uv run devops ci test tests/test_argo_credentials.py",`, and its `test` text holds no code span, so the group names no test module and the rule refuses it.
- The rule's text is `src/devops_cli/lang/en/messages.py:4943:which runs no test module of the`, and `src/devops_cli/roadmap/stage/stage_eval_gates.py:419:holds_message = not defect.message or any(defect.message in problem for problem in problems)` matches a defect's `message` as a substring of a gate problem, so the defect carries the words `which runs no test module of the group`.
- `src/devops_cli/roadmap/stage/stage_eval_gates.py:431:caught = bool(found) and _explains(found, defect)`, and `_explains` also requires each path of `defect.paths` in backticks, so the defect keeps `paths` empty and is judged by its message alone.
- `src/devops_cli/roadmap/stage/stage_eval_cases.py:90:VERIFY_FORM = "verify_form"` is the type of the form rule, and the staged enum holds no member `verify_test`.
- `read_file` of `tests/fixtures/roadmap_eval/stage/2576-a-token-that-argo-cd-refuses/case.json` read its defect list: its defects have the types false_premise, other, missing_path, criterion_dropped, spec_delta_wrong, other and false_premise, and none is `verify_form`.
- The staged constants that the plan relies on: `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:56:JUDGED_BASELINE: Final[tuple[int, int]] = (82, 319)`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:278:assert counts[DefectType.VERIFY_FORM] == (6, 0, 12)` and `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:263:assert len(defects) == 76`, so one caught `verify_form` defect gives (83, 320), (7, 0, 12) and 77.
- The command module pins the same totals: `tests/roadmap/stage/test_roadmap_stage_eval_command.py:81:assert "Defects that a gate judges: 82 of 319 (26%)." in result.output`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py:100:assert report["defects"] == {"judged": 82, "known": 319}` and `tests/roadmap/stage/test_roadmap_stage_eval_command.py:103:== (6, 0, 12)`, so they become 83 of 320, which `src/devops_cli/roadmap/stage/stage_eval_render.py:def _percent` prints as 26%, and (7, 0, 12).
- `search_code` for `319`, for `report.judged()` and for `len(defects) ==` found these pins only in those two modules and in change folders, so the group moves every pinned total.
- `tests/roadmap/stage/test_roadmap_stage_eval_gates.py:def test_the_gates_and_the_pending_gates_cover_each_type_once_but_those_no_gate_judges` requires every `DefectType` member to be caught by a gate, pending, or unjudged, so a new `verify_test` member would need gate code that this issue forbids; `VERIFY_FORM` at the `paths` gate judges the defect as it stands.
- `src/devops_cli/roadmap/stage/stage_change.py:def _security_search_texts` scans only `what_changes`, the group paths and the task texts for a trigger word or a trigger path, and none of them holds one now, so `security` is empty.
- The group changes three files that exist at the staged commit, and its task text names only those files and the symbols of the check, so the plan names no path that the staged tree lacks; the recorded plan's verify path appears in no task text, `changes`, `creates` or `reads` of this plan.
- First check before the edit: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py` passes at the staged commit, and it fails after the case change on the new test and on the counts until the group moves them; `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_command.py` passes at the staged commit and fails after the case change until its totals move.
- The plan calls no function that needs a checkout, a client or a network: the replay reads the case files under `tests/fixtures/roadmap_eval/stage/` and starts no process.
- The plan introduces no command and no verify program. Its one verify is `uv run devops ci test`, whose programs `uv`, `python` and `pytest` are in the runner image, and the replay opens no network, no cluster and no scanner; the pod settings apply unchanged, with `readOnlyRootFilesystem` true and `runAsNonRoot` true.

## Existing Tool Considered

The golden-set replay of the stage job already runs every gate on every recorded plan: `replay_all` and `replay_case` in `src/devops_cli/roadmap/stage/stage_eval_gates.py`, with the cases under `tests/fixtures/roadmap_eval/stage/`. The change labels one recorded case and builds no tool.

## Dependencies

- #3463: Its rule that refuses a behavior group whose verify runs no test module of the group is the precondition of this case; it is closed (completed) and released in v0.138.0, and the rule is at commit 65268d6f of the staged tree.

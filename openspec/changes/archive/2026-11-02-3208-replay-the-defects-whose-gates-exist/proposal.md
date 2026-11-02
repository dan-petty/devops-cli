# Proposal

## Why

Issue #3208. `devops roadmap eval stage --replay` listed 67 of the 299 known defects of the golden set as waiting for a gate: `ignores_existing_code` 23 (#3012), `verify_form` 12 (#3015), `spec_delta_wrong` 24 (#3013) and `task_order` 8 (#3017). Those four issues are merged, but `PENDING_GATES` still named the types, and the cases marked the defects `pending`. The replay said "every gate refuses what it must refuse" while it judged 60 of 299 defects. A change to a gate could not state a score before and after for the rest.

## What Changes

- Each of the 67 pending defects now has a decision from a run of the replay: the `paths` gate catches it, or the recorded plan cannot show it and the defect has the gate `none` and a `reason`.
  - `paths` catches 4 more defects of `spec_delta_wrong`: 2162, 2369, 2371 and 2373. Each is a delta on a change that only touches `tests/`, `.github/workflows/`, `docs/` or `openspec/`, and the problem says "These paths need no spec delta". The 5th defect of this type (2116) was labeled before. The 4 defects of `verify_form` that `paths` catches (2116, 2260, 2369 and 2462) were labeled before.
  - `ignores_existing_code` (23): none is visible to a check on the reply. #3012 (`collect_context`) puts the tests and callers of a cited symbol into the model input and adds no check, so the gate is `none`.
  - `task_order` (8): none is a path that a later group creates, which is all that #3017 (`path_problems`) refuses. Each is a test or code that a later group provides, so the gate is `none`.
  - `spec_delta_wrong` (20 more) and `verify_form` (12): a wrong capability, an open decision, a command that cannot fail, a test file that the plan names in the tasks and not in `creates`, or a delta on `pyproject.toml`, `SECURITY.md` or code under `src/`, which the rule for a delta that is not needed does not list. The gate is `none` with a reason.
- `PENDING_GATES` is empty. A `pending` label on any type now fails the replay as stale.
- The `paths` gate stays one gate: it is `check_proposal`, which the job runs as one check, so it judges `missing_path`, `spec_delta_wrong` and `verify_form`. A separate gate for `verify_form` would only split the problems of one call, and the live score would then count a missing path as a catch of a form defect.
- A defect has an optional `reason`. A test holds that every defect of a type that waited for a gate and has the gate `none` gives a reason.
- The replay report prints, for each type of defect, the defects that a gate caught and missed, the defects that wait for a gate and the defects that no gate judges, and then the share of all known defects that a gate judges: 64 of 299 (21 percent), up from 60. The JSON report holds the same counts. The line for the types that wait for a gate prints only when one waits. The gate table drops its defect-type column, since `paths` judges three types.
- `docs/ROADMAP_WORKFLOW.md` states the gates, the `reason` and the new report.
- The change alters a command output, so it carries a spec delta. It modifies three requirements and adds one.
- No `plan.json` is edited and no plan is invented: only the gate, the message and the reason of a defect change.
- The change fits one pull request.

### Out of scope

- A check on the reply for code that exists (#3012 builds none), and for an order of the work that is not a path (#3017 refuses only a path). Both are limits of the gates. This change records them in the data and builds no check.
- Gaps in the rule for a delta that is not needed (it does not list `pyproject.toml` or documents at the root): #3212. The reasons in `case.json` name them.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage-eval`: MODIFIED requirements for the golden set, the replay and the defects that wait for a gate. ADDED requirement for the counts by type.

## Impact

- Code: `src/devops_cli/roadmap/stage_eval_cases.py`, `src/devops_cli/roadmap/stage_eval_gates.py`, `src/devops_cli/roadmap/stage_eval_render.py`, `src/devops_cli/lang/en/messages.py`.
- Data: 34 `tests/fixtures/roadmap_eval/stage/*/case.json` files (labels only).
- Documents: `docs/ROADMAP_WORKFLOW.md`.
- Tests: `tests/roadmap/test_roadmap_stage_eval_gates.py`, `tests/roadmap/test_roadmap_stage_eval_command.py`, `tests/roadmap/test_roadmap_stage_eval_run.py`.

## Feasibility

Checked on 2026-11-02 on `main` at the commit of release 0.44.0 (a plain clone, Python 3.14.6):

- Baseline: `uv run devops roadmap eval stage --replay` exits 0 and prints `paths` 36 known, 36 caught; `kind` 24, 24; 23 `ignores_existing_code`, 12 `verify_form`, 24 `spec_delta_wrong` and 8 `task_order` waiting; no gate judges 172 (`other` 98, `false_premise` 59, `criterion_dropped` 12, `contrived_test` 3). That is 60 judged of 299.
- The checks exist: `check_proposal` in `stage_change.py` runs `_delta_problems` (#3177, with `_needs_no_spec`), `form_problems` from `stage_form.py` (#3189) and `path_problems` from `stage_paths.py` (#3010, with the forward read of #3179). #3178 changes `collect_context` in `refine.py`, not `check_proposal`.
- One premise of the issue was wrong: "the checks exist inside `check_proposal` now" holds for `spec_delta_wrong`, `verify_form` and the forward read, and not for `ignores_existing_code`, which #3012 delivered as model input.
- Each pending defect was run through `PlanUnderTest.of_case` and the pieces of `check_proposal` (`_delta_problems`, `form_problems`, `path_problems`), and the problems were read next to the text of the defect. A defect is judged only when a problem gives the reason that the defect states. A problem for the same plan with another reason does not count, as the plan of 2167 has a delta that the rule refuses, while the defect is the wording of its requirement.
- The facts file holds a thinned tree and the capability names: no base spec text and no code. So a defect about existing code, a base spec or an order of the work in a group cannot reach a gate.
- Result after the labels: `uv run devops roadmap eval stage --replay` exits 0 and prints `Defects that a gate judges: 64 of 299 (21%).`

## Existing Tool Considered

The replay of #3028 is the tool, and this change only labels its data and counts its output. No open tool relabels a fixture set of this shape. Written cost: about 90 000 tokens and 2 hours to run the replay for each defect, read the 67 texts and write the labels and the reasons; about 3 000 tokens a year to keep the counts when a gate changes; nothing new to fix. It deletes no code.

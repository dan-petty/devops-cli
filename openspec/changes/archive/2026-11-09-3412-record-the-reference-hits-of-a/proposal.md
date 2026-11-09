# Proposal: #3412

## Why

`devops roadmap eval stage --replay` runs the recorded plans through `check_proposal` and reads no git. The reference check of #3373 reads the hits that the job probes from the staging commit, and the replay passes no such hits, so it cannot judge the check. A plan that misses a reference hit passes the replay after #3373 landed, and the check has no regression case in the golden set (#3028).

## What Changes

- Add a `references` key to `facts.json` of a stage case: the paths of the files that hold the old path or the dotted name of a moved module. A case with no such key reads an empty list, so every existing case keeps its verdict.
- Add a `references` field to `PlanUnderTest` of `src/devops_cli/roadmap/stage/stage_eval_gates.py`, set it from the facts of the case in `of_case`, and pass it to `check_proposal` from the `paths` gate.
- Add one stage case whose plan moves a module and leaves a string literal of the old name in `tests/`, with one `missing_path` defect that names the test file and the gate `paths`.
- Raise the case and defect counts that the tests pin, and add tests for the recorded hits and for the empty default.
- Archive the change folder in the last commit of the pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage-eval`: the golden set records the reference hits of a case and the replay passes them to the reference check.

## Impact

- `src/devops_cli/roadmap/stage/stage_eval_cases.py`
- `src/devops_cli/roadmap/stage/stage_eval_gates.py`
- `tests/fixtures/roadmap_eval/stage/3412-a-move-plan-leaves-a-test-reference/`
- `tests/roadmap/stage/test_roadmap_stage_eval_cases.py`
- `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`
- `tests/roadmap/stage/test_roadmap_stage_eval_command.py`

## Feasibility

- `read_file` of `src/devops_cli/roadmap/stage/stage_eval_gates.py` showed `_path_gate` at line 200: it calls `check_proposal` with `search_evidence`, `manifest_references`, `constants`, `models` and `trace`, and no `references`.
- `read_file` of `src/devops_cli/roadmap/stage/stage_change.py` showed `check_proposal` at line 1832 and `check_gates` at line 1770: both take `references: Sequence[str] = ()` and `_move_reference_problems` at line 972 refuses each probed reference that no group changes and that the reply does not mark unchanged.
- `read_file` of `src/devops_cli/roadmap/stage/stage_eval_cases.py` showed `CaseFacts` at line 167 with `tracked`, `capabilities`, `search_evidence`, `manifest_references`, `constants`, `models` and `trace`, and no `references`, so a `facts.json` with the key fails the model and the set does not load.
- `read_file` of `src/devops_cli/roadmap/stage/stage_eval_gates.py` showed `PlanUnderTest.of_case` at line 96 copying `search_evidence` and `manifest_references` from the facts, so the recorded hits need the same field and copy.
- `search_code` for `references` in `src/devops_cli/roadmap/stage/` showed the job side of #3373 at `stage.py:1407` (`_probe_references`) and `stage_change.py:972` (`_move_reference_problems`), and no read of the facts on the replay side, so the premise holds.
- `read_file` of `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` showed the replay fixture loads `CASES` at import and the count baseline `JUDGED_BASELINE = (80, 316)` at line 54; the new case adds one judged defect and one defect.
- `read_file` of `tests/roadmap/stage/test_roadmap_stage_eval_cases.py` showed the counts `(EVALUATED_PULLS, 55, 5)` at line 65 and `len(EVALUATED_PULLS) == 50` at line 66; the new case adds one reviewed case and one pull.
- `read_file` of `tests/roadmap/stage/test_roadmap_stage_eval_command.py` showed the literals `55 case(s), 5 good` at line 78 and `80 of 316` at line 81, which the new counts change to `56` and `81 of 317 (26%)`.
- `references` with `devops_cli.roadmap.claim` returned 2 files and 2 lines in `tests/`: `tests/roadmap/test_roadmap_claim.py` line 17 and `tests/roadmap/test_roadmap_claim_command.py` line 11, so the new case names two real test files that hold the old dotted name.
- The first check of the implementation is `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_cases.py tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, which replays the set offline.
- The replay reads no git: `load_cases` reads the case files and `PlanUnderTest.of_case` builds the tree from `facts.json`, so the new case reads the recorded hits and no commit.

## Existing Tool Considered

No open tool or library supplies the schema of a stage case. The case files already carry the facts of a case in `facts.json`, and the change extends that file and the model that reads it. The written cost is about 3k tokens and 45 minutes to build, keep and fix, and the change adds no tool.

## Dependencies

#3373, which landed on `main`: `check_proposal` takes the reference hits and `_move_reference_problems` refuses a missed hit.

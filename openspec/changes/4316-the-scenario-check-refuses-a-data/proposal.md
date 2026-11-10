# Proposal: #4316

## Why

The scenario check refuses a spec scenario that names a data file as a condition (#4316). `_scenario_problems` in `src/devops_cli/roadmap/stage/stage_change.py` takes each code span of the `when` and the `then` that is a repository path or a code identifier, and needs a behavior test that names one of them. A scenario that says what a fixture holds, such as "`.github/labels.yml` declares no `scope/floor`", names the file as input data, and the test builds that data in memory. A live stage run on #3599 with the live stage model was refused with "Scenario 'A scope that no label declares' names `.github/labels.yml` with no behavior test." The stage job logs of 2026-11-04 to 2026-11-09 hold 8 such failures. Closes #4316.

## What Changes

- The check judges the code spans of the `then`, and the code spans of the `when` that are no path or whose path a behavior group changes, creates or reads.
- A path in the `when` that no behavior group touches is input data and needs no test text.
- A `then` that names code with no behavior test is refused as before.
- The change carries a spec delta because it changes which plans the stage job refuses.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: A scenario that names code has a behavior test

## Impact

- Code: `src/devops_cli/roadmap/stage/stage_change.py`
- Tests: `tests/roadmap/stage/test_roadmap_stage_scenario_evidence.py`

## Feasibility

- The cause is in the code: `_scenario_problems` put every path and identifier of `when` and `then` into one list and refused the scenario when no behavior test named any of them. The scenario of the live run is the test input.
- The failure text of the live run is in the logs: "Scenario 'A scope that no label declares' names `.github/labels.yml` with no behavior test." and the `when` "the title of the issue is `fix(floor): the job drops a comment` and `.github/labels.yml` declares no `scope/floor`".
- First check against the real system: `uv run devops roadmap eval stage --replay`, which keeps 81 of 317 defects caught by a gate, 0 missed, and 5 of 5 good plans accepted. The 24 `contrived_test` defects stay caught.
- Second check: `uv run devops ci test tests/roadmap/stage/test_roadmap_stage_scenario_evidence.py`.

## Existing Tool Considered

No library judges a scenario of a spec delta, and the project holds no such helper. The change moves the choice of spans into one function. Cost: about 25 000 tokens to build, 3 000 to keep and 1 hour. The change deletes no internal code.

# Tasks

## 1. Add the premise probe

Reads: `src/devops_cli/roadmap/stage_tools.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/stage_probe.py` (new), `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_probe.py` (new).

- [ ] 1.1 tests/roadmap/test_roadmap_stage_probe.py, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_probe.py` fails on the base
- [ ] 1.2 Add `stage_probe.py` with `cited_items(body)` that returns the backtick-quoted paths and identifiers, and `probe_premise(source, sha, body)` that runs at most `CONST_ROADMAP_STAGE_PROBE_MAX_COMMANDS` read-only git commands and returns the probe text with the skipped probes. Add the constant and the messages. Write the test first, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_probe.py` passes

## 2. Put the probe output in the model input

Reads: `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_probe.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 2.1 tests/roadmap/test_roadmap_stage_plan.py, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 2.2 Call `probe_premise` in `_Planner._request` and add its text under the `probes` key of the request. Write the test first: the request of an issue that cites a path holds the probe text, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 3. Return the item on a false premise

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/return_item.py`, `tests/roadmap/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/roadmap/stage.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 3.1 tests/roadmap/test_roadmap_stage_plan.py, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 3.2 Add the `premise_failed` field to `StageProposal`. In `_Planner.plan`, when the reply holds it, return the item with `devops roadmap return <issue> --comment <evidence> --confirm` and open no pull request. Write the test first: a reply with `premise_failed` returns the item and opens no draft, and verify that `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 4. Ask feasibility to quote the probe output

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`.

- [ ] 4.1 Change the `feasibility` rule of the prompt to ask for a quote of the probe output, and to say `premise_failed` with the evidence when a probe shows a false premise, and verify that `uv run devops ci docs` passes

## 5. Record the spec delta

Reads: `openspec/specs/roadmap-stage/spec.md`. Changes: `openspec/changes/3011-stage-premise-probe/specs/roadmap-stage/spec.md` (new).

- [ ] 5.1 Write the spec delta of `roadmap-stage` with the three added requirements and their scenarios, and verify that `openspec validate --strict` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).

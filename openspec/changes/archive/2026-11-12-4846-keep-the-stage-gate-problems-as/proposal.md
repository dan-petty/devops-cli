# Proposal: #4846

## Why

Issue #4846: the stage job joins the gate problems of a refused reply into one string before the return (`_settle` in `src/devops_cli/roadmap/stage/stage.py`). The return loop cannot tell which problems are gone, new or stuck, and no fixable check can class them. The kept refused records hold problems whose fix rates per kind go from 0 of 17 (a stale test path) to 46 of 46 (a stale citation).

## What Changes

- The gates give `StageFinding` items: the gate, the code, the path and the text of each problem. The code is the key of the message in `MESSAGES.roadmap` that the text matches (`stage_findings.py`). A refusal outside `check_gates` has the code of its check: `title`, `body` or `validate`.
- The model gets the same problem text as before: the texts of the findings in the order of the gates, joined by one space.
- The refused file `<n>.refused.json` keeps the findings of each refused reply.
- The line `stage gate returns:` adds `gates=` and `codes=` with the counts of the last refused reply. Each reply after a return logs `stage gate findings:` with the findings before, gone, stuck (same gate and same text with the digits masked) and new.
- The histogram `devops_cli_roadmap_stage_gate_problems{repo, reply}` observes the count of findings of each reply that the checks judge.
- `stage_finding_classes.json` holds, for each code of 42 saved refused plans, its gate, its fix class (`mechanical`, `model_fixable`, `low_share`, `never`), its seed fix rate, the sample count and the Wilson lower bound.
- These are observable log lines, a metric and a file, so the change has a spec delta in the new capability `roadmap-stage-findings`.

## Capabilities

- `roadmap-stage-findings` (new): the findings of the stage gates, the counts of a return, and the seed fix class of each code.

## Impact

- `src/devops_cli/roadmap/stage/stage_findings.py` (new), `stage_finding_classes.json` (new), `stage.py`, `stage_plan_record.py`, `src/devops_cli/roadmap/round_log.py`, `src/devops_cli/telemetry/instruments.py`, `docs/TELEMETRY.md` (generated), `k8s/README.md`.
- Tests: `tests/roadmap/stage/test_roadmap_stage_findings.py` (new), `test_roadmap_stage_refused_reply.py`, `test_roadmap_stage_repair_return.py`, `tests/telemetry/test_roadmap_stage_steps.py`, the reset of the template cache in `tests/conftest.py`, and the fixture `tests/fixtures/roadmap/stage_refused_findings.json`.
- No prompt text, gate, cap or setting changes. The change fits one pull request.

## Feasibility

- `check_gates` (`stage_change.py`) returns the problems of each gate under its `ProposalGate`, and `_gate_problems` flattened them with `joined_problems`, so the gate of each problem is known before the join.
- Each gate problem is a template of `MESSAGES.roadmap`: the 61 keys that start with `stage_problem_` each give their own key as the code when a test fills their fields. 231 templates of `MESSAGES.roadmap` that start with `stage_` hold at least 12 characters of literal text.
- The 42 kept refused records (4 snapshots of the Service volume, 2026-11-10 to 2026-11-11) hold 438 problems in their replies, and each problem gets a code, none `uncoded`. Their 44 returns hold 256 findings before the return: 212 gone, 44 stuck and 144 new. The stale test path is 0 of 17, the caller 11 of 28 and the stale citation 46 of 46, the same rates that the stage drought study measured with hand rules.
- `statsmodels==0.15.0` is a locked dependency (`pyproject.toml`), and `proportion_confint(method="wilson")` gives the lower bound.

## Existing Tool Considered

- The standard parser of format strings, `string.Formatter.parse`, gives the literal text and the fields of each message, so no hand rule per message is written. The `parse` library (the reverse of `format`) covers the same need, but it adds a dependency for one call.
- `statsmodels` `proportion_confint` gives the Wilson lower bound. No new library.
- The change deletes the use of `joined_problems` in `stage.py`; `check_proposal` still uses it.
- Cost: about 0.8M tokens and half a day to build; the guard tests keep each gate message coded.

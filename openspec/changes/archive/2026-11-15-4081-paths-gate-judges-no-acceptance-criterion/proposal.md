# Proposal: #4081

## Why

`_path_gate` in `src/devops_cli/roadmap/stage/stage_eval_gates.py` returns every problem of
`check_proposal`, the criteria rule included. The eval system gives each rule its own gate, so a
criterion problem appears under `paths` as well as under `criteria`. A plan with no `issue_body`
reaches the criteria rule with an empty body, and any rule that refuses a criterion it cannot
match then fails the paths gate. Closes #4081.

## What Changes

- `_path_gate` calls `check_gates` and joins every gate but `criteria`, so a criterion problem
  appears only under the `criteria` gate.
- Add a regression test: a plan with a criterion left out and a plan whose criterion names a
  group above the group count both give empty `paths` problems and their criterion problems under
  `criteria`.

## Capabilities

`roadmap-stage-eval`: the replay requirement now names the criteria rule as the one gate that
`paths` leaves out.

## Impact

The stage eval replay. No command, option, message, manifest or image changes. The stage job
itself does not use the gate table.

## Feasibility

Premise checked on 2026-11-15 against `origin/main` (ca62d6a9f): `_path_gate` returns
`check_proposal`, which joins the criteria rule (`criterion_problems`); the eval cases load and
the gates run with no model call. The new test fails before the change and passes after it.

## Existing Tool Considered

pytest, a dev dependency, replays the recorded cases through the gates. No new tool.

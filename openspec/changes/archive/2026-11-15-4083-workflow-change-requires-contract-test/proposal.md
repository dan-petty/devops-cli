# Proposal: #4083

## Why

The stage planner can put an edit of `.github/workflows/ci.yml` in one group and the workflow
contract test in a later group, or in no group. The group then verifies the workflow with
actionlint and zizmor, which pass on the base commit and read no step of the change. AGENTS.md
rule 4 asks for the test first, and the contract test is the executable test of a workflow
change. Closes #4083.

## What Changes

- `path_problems` in `src/devops_cli/roadmap/stage/stage_paths.py` reports a problem for each
  `.github/workflows/*.yml` file that a group changes when the `changes` of that group holds no
  `tests/invariants/test_workflow_contracts.py`.
- A message, `roadmap.stage_problem_workflow_contract`, names the group, the workflow and the
  contract test.

## Capabilities

`roadmap-stage/paths-gate`: one new requirement for the workflow contract rule.

## Impact

The stage job and the stage eval replay. No command or option changes. The golden set holds no `good` plan that changes a workflow, so the replay still
passes.

## Feasibility

Premise checked on 2026-11-15 against `origin/main` (ca62d6a9f): `path_problems` holds no rule for
`.github/workflows/`, and the case `2163-coverage-measures-branches-and-ci-keeps` holds a group
that changes `.github/workflows/ci.yml` with no contract test. The new tests fail before the
change and pass after it.

## Existing Tool Considered

The rule extends `path_problems`, which the stage job already calls. actionlint and zizmor read
the syntax of the workflow only, so they cannot replace the contract test. No new tool.

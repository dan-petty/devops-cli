# Design: #4083

## Context

`path_problems` reads the groups and the staged tree and returns the problems of a plan. The stage
job passes it the tree at the staging commit; the eval replay passes it the tree of the case. A
workflow change is an `other` group, so it has no `test` field, but it can list any path in
`changes`.

## Decisions

- The rule lives in `workflow_contract_problems`, a new function that `path_problems` calls. The
  function reads `changes` only, so a group that reads a workflow and changes no workflow needs no
  contract test, and the `reads` of a group do not satisfy the rule.
- The workflow directory and the contract test path are module constants,
  `WORKFLOW_DIRECTORY` and `WORKFLOW_CONTRACT_TEST`, so the prompt test reads the same text as the
  rule.
- The message names the group, the workflow and the contract test, so one sentence is enough to
  repair the plan.

## Risks

- A change that edits no contract test but is covered by an existing assertion in
  `tests/invariants/test_workflow_contracts.py` still needs the file in `changes`. The prompt says
  so, and a pin bump that an existing assertion holds fails the rule. The owner can relax the rule
  if that case becomes common.
- The rule reads the suffix `.yml` only, as the repository holds no `.yaml` workflow.

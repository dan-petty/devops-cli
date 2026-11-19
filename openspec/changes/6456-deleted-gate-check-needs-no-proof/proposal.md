# Proposal: #6456

## Why

A fix that removes a manifest rule must also delete the gate check that asserted that rule. The
`Fail-to-Pass Check` then fails, because `devops ci fail-to-pass` replays the gate row of each
changed module under `tests/gate/*_checks/`. The base run uses the tests of the head, so the
deleted check runs on neither tree, and no case can fail on the base and pass on the head.
`docs/TESTING.md` says that a deletion gets no test, and that no Fail-to-Pass rule asks for a test
of a manifest or a config value (#6080, #6207). The check and the documents disagree. Closes #6456.

## What Changes

- A changed gate check module "only loses checks" when its head keeps the top-level statements of
  its base in the same order with some left out, at least one left-out statement is a
  `def check_*`, and each left-out statement is an import, an assignment to names, a function or a
  class whose names the head does not use. The command compares the statements by syntax tree,
  so a comment or a blank line changes nothing. A changed check, helper, constant, decorator,
  `parametrize` label or import, an added statement and a moved statement make the module
  changed, as today.
- A fix that changes no source code, and whose changed gate check modules all only lose checks,
  needs no proof. `devops ci fail-to-pass` passes with no replay and names each deleted check as
  `<module>.<check>`, the name that the gate runner gives a case.
- A module that only loses checks starts no gate row. The other changed modules keep their
  replay, and a fix that changes source code still needs a proof.
- A new module, a renamed module and a module that does not parse keep the replay. A deleted
  module stays out of the replay, as it is today.
- The command output and its exit status change, so the change has a spec delta.

## Capabilities

### Modified

- `ci-fail-to-pass`: a gate check module that only loses checks needs no proof, and starts no gate
  row.

## Impact

The fix of #6439 (pull request #6459) gets a green `Fail-to-Pass Check` with no new test. A fix
that adds or changes a gate case still needs a case that fails on the base and passes on the head.
The workflow, the dry run and the replay of test files do not change. The change fits one pull
request.

## Feasibility

Confirmed against the code on `origin/main` 7dd00afe7 and against the branch of #6439.
`run_fail_to_pass` in `src/devops_cli/ci/fail_to_pass.py` sets `needs_proof=False` only when
`changed_tests` lists no source file and no gate check, and `changed_tests` lists each added or
modified module under `tests/gate/*_checks/` with no look at its content. On the branch
`fix/6439-exclude-gateway-caller-labels`, `uv run devops ci fail-to-pass --base origin/main`
prints `k8s gate row: 0 of 177 cases failed on base, 0 of 177 on head
(tests/gate/k8s_checks/llm_gateway.py)` and exits 1. That branch changes no file under `src/`. In
`tests/gate/k8s_checks/llm_gateway.py` it deletes
`check_the_gateway_endpoint_drops_the_caller_labels` and the constant `SERVICE_MONITOR`, and
changes the text of a comment. A probe with `ast.parse` and `ast.dump` found that the top-level
statements of the head are the statements of the base in the same order with these two left out,
and that the head uses no name that they bind. So the rule accepts that module. The gate runner
(`tests/gate/runner.py`) finds the top-level functions named `check_*` of a module, and names a
case `<module>.<check>`. `changed_tests` lists no deleted path, so a deleted check module is not a
changed gate check now.

## Existing Tool Considered

Python's `ast` module, which `src/devops_cli/ci/changed_tests.py` already uses to tell a changed
test from an unchanged one (#3124, #6372). It parses each side, and `ast.dump` with no line
numbers gives a statement that a comment or layout does not change. Griffe finds removed objects
of a Python API, but it compares signatures and ignores the bodies of functions, so it cannot see
a changed check or helper. A text diff cannot tell a deleted check from a deleted line in a kept
check. No open tool decides whether a module only loses functions. The change adds one function of
about 40 lines to `changed_tests.py` and a field to the report. It costs about 6,000 tokens and
one hour to build, and about 1,000 tokens to keep.

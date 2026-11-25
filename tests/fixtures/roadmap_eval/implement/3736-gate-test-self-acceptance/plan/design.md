# Design

## Context

See proposal.md for the cause (#3736). The self-acceptance rule of #3404 and the gate test of #3732 meet for the first time on `main`.

## Goals / Non-Goals

**Goals:**
- Make the gate test fail only for the gate it names.

**Non-Goals:**
- Change the self-acceptance rule or the gates.

## Decisions

### 1. The test gives its group the self-acceptance test

- **Decision**: Set the `test` field of the changed group to a sentence with the three marks of the rule.
- **Alternative considered**: Change a file other than `stage_change.py` in the test.
  - *Rejected*: The gate `eval-replay` fires for the stage check modules, and `stage_change.py` is the one the test names. The test should keep it.

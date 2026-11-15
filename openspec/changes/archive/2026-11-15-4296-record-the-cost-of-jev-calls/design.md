# Design: #4296

## Context

`track_request_spend` prices a call from the tokens and the pricing registry, writes the ledger
row and emits the metrics. The agent hook calls it, but `DecisionModel.decide` is called
directly, so no hook runs. The ledger treats a call with provider `gateway` and a served model
as hosted, and prices it at the served model.

## Decisions

- `record_jev_spend` lives in `src/devops_cli/ai/jev.py`, beside `decide_with_jev`, which calls
  it. `intake_jev` imports it inside the decision function, so the import graph keeps no cycle.
- The wrapper passes `served_model="typesafe/jev-1.14"` with provider `gateway`, so the ledger
  prices the call as hosted and not as local savings.
- The price is a built-in entry of `_HOSTED_GROUP_PRICES`, so a workstation with no setting
  prices it, and a test that builds the registry with no settings sees it. The ConfigMap sets the
  same rates for the cluster.
- The wrapper catches the errors that a ledger or a settings file can raise (`OSError`,
  `RuntimeError`, `TypeError`, `ValueError`, `KeyError`) and returns: the spend record is a report,
  and the answer is the product of the call. The `except` holds a comment because the caller sees
  no result.

## Risks

- Every Jev test now writes one ledger row into the isolated HOME. The row costs one SQLite
  write and no test asserted an empty ledger.
- The cost is stored at 6 decimal places, so one call of 64 input tokens stores 0.000003 USD.

# Design

## Context

`_record` in `factory.py` reads `served_by` from the model and uses it for the server, but it leaves the ledger column NULL. `_QUERY_BACKEND_BREAKDOWN` filters on the column.

## Goals

- Count every served request in the backend breakdown.
- Price a request at its served backend.

## Decisions

- **Pass the value.** One argument joins the fields the ledger already stores.
- **The price follows `is_local`.** A local gateway host makes the request local, and a hosted backend makes it hosted. The two price tests now name a hosted backend, which is what they intend to test.

## Risks

- A request through a local gateway now prices at zero. That is the rule of #1631 and #3656.

## Tests

- A `build_agent` request with a `served_by` appears in the backend report with that URL.
- The two price tests keep their costs with a hosted backend.

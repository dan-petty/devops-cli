# Proposal: #4412

## Why
Three routes of an `issues` webhook end after the scoped intake, so `refine`, `retitle`, `stage` and `implement` wait for their timers. An edit of an Item that holds a `priority/*` label wakes no model-lane round. A P0 placement stamps `refine_due`, and no model-lane worker wakes. A `labeled`, `unlabeled` or `closed` trigger wakes every lane, and no row declares the key, so no row runs. Closes #4412.

## What Changes
- A row declares the `issues` keys that make it due: `refine` (`edited`, `labeled`, `unlabeled`), `retitle` (`edited`), `stage` and `implement` (`labeled`, `unlabeled`, `closed`).
- After the scoped update of an edit, or of a critical or P0 placement, the Service enqueues the delivery key on the model lane alone. `enqueue_trigger` takes an optional lane.
- The scoped-update spec and step 8 of `k8s/README.md` name the triage lane, which runs the scoped update. They were wrong: they said the model lane.

## Capabilities
Modified: `roadmap-scoped-updates`.

## Impact
The model lane and the status lane run `refine`, `retitle`, `stage` and `implement` at once after an edit, a label change or a close of an issue, as the interval allowed before. A person's label change costs one model-lane round. The Service's own writes stay refused, so no loop follows. The stateless router (#4575) replaces the lane choice later, and this change keeps the new code in two small functions.

## Feasibility
Checked in the code of `main` at 818ac6f3. `SCOPED_UPDATES` maps `("issues", "edited")` to the triage lane. `_Poll.is_due` runs a row by interval, by `batch_keys`, by `refine_due` or by a due rule. Only the `intake` row declares `batch_keys`. The consumer already refuses a delivery of the App's own bot (`refuse_own_write`). The test of the `labeled` key fails on `main`: no row runs.

## Existing Tool Considered
`gidgethub` (ADR 0006) parses the payloads. It does not schedule the lane workers or read `schedule.json`. ADR 0008 and ADR 0009 rejected Argo Events for the Service. The change builds on the existing rows. Cost: about 90,000 tokens to build, keep and fix, and 2 hours of elapsed time.

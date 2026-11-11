# Design

## Context

The Service runs one pod with the `Recreate` strategy. A release, a ConfigMap change or a node drain stops the pod about 19 times a day. Each lane of each repository runs one round at a time in a worker thread. A round runs the due rows of its lane in order. The stage and refine rows take their items one at a time and write each item when it is done (#3631, #4034).

## Decisions

- **Two bounded phases.** Phase 1 sets the stop and waits up to `CONST_SERVICE_STOP_DRAIN_SECONDS` for the worker threads. Phase 2 cuts the budget and waits up to `CONST_SERVICE_STOP_CUT_SECONDS`. `drain_and_stop` returns whether every worker stopped.
- **Where the stop is read.** The worker reads its own stop event before it pops a batch. The row loop of `_execute_due_rows` reads `service_stopping()` before a due row starts. `_plan_each` (stage) and `plan_refine` read it before each item, through `raise_if_service_stops`. Each check sits at a boundary where the work before it is written, so the stop path loses nothing.
- **A row that does not start.** The round ends with `ServiceStoppingError` and counts nothing for that row: no job, no failure, no success. The row stays due, so the next pod runs it. When an earlier row of the round failed for a real reason, the round ends with that failure, as before.
- **The cut.** `RequestBudget.cut()` makes `admit` raise `ServiceStoppingError` for every request, also when the window has room. A round in flight then ends at its next GitHub request through the stop path. A round that sends no request, such as a model call that runs long, stops with the process at the end of the grace period. That is the rest of the risk, about 7% of the stops that fall in a stage item.
- **The numbers.** 600 s from the plan step times (Feasibility of the proposal). 30 s for the cut: a GitHub request ends within its own timeout, and the stop path writes at most the failures of the items done. The grace period of 660 s adds 30 s for uvicorn and the exit. A test holds the manifest to `CONST_SERVICE_STOP_GRACE_SECONDS` and the constant above the sum of the two waits.

## Rejected alternatives

- **Keep the setting `service.drain_timeout_seconds`.** The grace period of the manifest cannot follow a setting, and the live ConfigMap and the owner's config file set 120, so the fix would not apply until a person changed both.
- **Cut the model calls too.** The stage planner calls the model through the pydantic-ai toolbox (`stage_toolbox.py`), not through `network.model_call_slot`, so a cut there needs a hook in the agent loop that refine and implement share. The item boundary and the 600 s wait cover about 93% of the stops that fall in a stage item without it.
- **A preStop hook.** uvicorn starts the drain on SIGTERM. A preStop hook runs before SIGTERM and uses the same grace period.
- **An Argo CD sync window.** It batches the syncs of the whole Application, self-heal included, and fixes reach the Service later. With the drain, a rollout no longer stops a round, so the window is not needed for this issue.
- **Wait for the whole round.** A stage row runs up to an hour (p99 3,723 s over 7 days). The item boundary bounds the wait by one item.

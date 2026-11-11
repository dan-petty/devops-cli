# Proposal: #4457

## Why

`devops roadmap explain <issue>` and `explain --json` report 0 tokens and 0 seconds for the last implement run when its trace is long. `trace_totals` adds the tokens and the seconds of the model events that the trace keeps. Since #4436 (issue #4393), `ImplementTrace.encode` drops the oldest model events first, so the bound drops every model event of a long run. The long runs are the runs that a reader most wants to explain. Closes #4457.

## What Changes

- `ImplementTrace.encode` keeps the sums of the events that it drops: `dropped_tokens` and `dropped_seconds` for the model events, and `dropped_repair_rounds` and `dropped_outcomes` for the attempt events. A sum of zero is not written, so a trace that fits the bound keeps its form.
- `decode` reads the sums. A trace with no sum, such as one from before this change, decodes with sums of zero. A sum that is not a number stops the decode with `TraceDecodeError`.
- A trace that is decoded and encoded again adds no sum twice: the decoded sums are the start of the sums of the next encode, the same as `dropped`.
- `trace_totals` adds the dropped sums to the sums of the kept events. The sums of a set of events come from one class, `TraceSums`, for the kept events and for the dropped events.
- The line beside the totals says that the totals include the dropped events.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-explain`: Totals of the last implement run; Dropped events beside the totals
- `roadmap-implement-job`: The job keeps the trace of its run

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_trace.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/roadmap/implement/test_roadmap_implement_trace.py`, `tests/roadmap/test_roadmap_explain.py`, `tests/roadmap/test_roadmap_explain_command.py`, `tests/support/roadmap_implement.py`
- Specs: `openspec/specs/roadmap-explain/spec.md`, `openspec/specs/roadmap-implement-job/spec.md`
- Documents: `docs/ROADMAP_WORKFLOW.md`
- The bound of the trace does not change. The sums take their characters from the bound, so a long trace keeps a few fewer events.

## Feasibility

- Source on `main` (`7234d718`): `trace_totals` in `src/devops_cli/roadmap/explain.py` sums only `trace.events`. `ImplementTrace.encode` in `src/devops_cli/roadmap/implement/implement_trace.py` sorts the model events first and drops them until the text fits.
- Command output on `main`: the run of the issue (100 model events of 20,300 tokens and 4 seconds, 150 shell calls, a failed attempt) gives `TraceTotals(tokens_total=2030000, seconds_total=400.0, ...)` for the full trace and `TraceTotals(tokens_total=0, seconds_total=0, ..., dropped=180)` after `encode` and `decode`. The decoded trace keeps 70 tool events, the attempt event and no model event.
- `implement.spend` holds the tokens of the run but no seconds, so it cannot give the seconds total.

## Existing Tool Considered

No tool applies: the change adds sums to a JSON value that the project owns. Cost to build: about 40k tokens and 1 hour.

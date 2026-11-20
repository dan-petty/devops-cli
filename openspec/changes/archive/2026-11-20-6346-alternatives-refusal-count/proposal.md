# Proposal: #6346

## Why

A refused alternatives check does not show its cause (#6346). The result line of a refused check gives `searches=0 returns=0`, but `_refusal_reason` returns `url` or `no_facts` only after an answered search, so the count of searches is wrong. The count of returns is a constant 0 too. No log line names the URL that a `url` refusal cites: the job record keeps only `alternatives.failed_reason`. Closes #6346.

## What Changes

- `CheckFailure` gets the field `searches`: the searches that a provider answered before the failure. Each failure of an agent run sets it from `AlternativesTools.searches`: a refused reply, a body marker problem, a stopped run, a failed model call and a failed read of the tools in use.
- `CheckFailure` also gets the field `returns`: the times that the run sent a refused reply back to the model (`_OutputChecker.returns`). Each failure of an agent run sets it.
- The result line of a failure gives `searches` and `returns` from these fields, in place of 0.
- When the job refuses a reply for reason `url`, it logs one WARNING for each source URL that no tool of the run returned, with the item number and the reason code. A refusal for another reason logs no URL.
- The result line and the log are observable, so the change carries a delta of `roadmap-alternatives`.

## Capabilities

- `roadmap-alternatives`: ADDED requirements 'A failed check logs its answered searches and its returns' and 'A url refusal logs each refused URL'.

## Impact

The result line of a refused or failed alternatives check gives the true count of answered searches and of returns. The service log holds the URL of each `url` refusal, so #6394 can measure the cause. No new step, gate, cap, retry or setting.

## Feasibility

- `src/devops_cli/roadmap/alternatives.py` on `origin/main` at 0f75e187c: `_refusal_reason` returns `no_search` when `tools.queries` is empty, before any `no_facts` or `url` return. `AlternativesWriter._log` writes the constant 0 for `searches` of each `CheckFailure`.
- Loki, the 24 hours before 2026-11-20 22:40 UTC: 25 alternatives result lines with `reason=url`, each with `searches=0 returns=0` (versions 0.182.1 to 0.185.0).
- Tempo, the trace of the devops-cli alternatives round that started 2026-11-20 at 22:19 UTC (version 0.185.0, items #4762 to #4806): each of its 15 agent runs called `search_web` 3 to 12 times.
- Loki, 7 days: only one line names a refused URL, the run error of a round in which every check failed. The skip line of the plan names it in no other case.

## Existing Tool Considered

The alternatives check of 2026-11-19 in #6346 found no tool: LLM observability platforms such as Logfire and OpenInference trace tool calls, but they do not compute the refusal reason of this job, its answered search count or the refused URL. The change stays in the project's own code: about 30k tokens and 2 hours to build, keep and fix. It deletes no internal code.

This change fits one pull request.

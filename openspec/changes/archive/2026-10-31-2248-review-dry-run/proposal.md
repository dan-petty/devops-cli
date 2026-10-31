# Proposal: Classify Review Commands and Add Request Plans in Dry Run

## Why

Issue #2248 describes that review commands do not follow the dry-run rule.
Commands that send external requests to LLM gateways, vector indices, or Valkey do not return request plans.
Commands that only inspect local files lack the `no-external-request` class.
Some commands have echo-only previews that print arguments.

This change delivers issue #2248 by classifying all review commands and adding request plans.

## What Changes

1. Decorate review commands with their dry-run classes:
   - `request-plan`: `review benchmark`, `review branch`, `review corpus generate`, `review corpus score`, `review intake`, `review path`, `review pr`, `review samples fetch`, `review samples validate`, `review score`, `review templates check`, and `review templates sweep`.
   - `no-external-request`: `review`, `review export-feedback`, `review findings`, `review rules test`, `review samples list`, `review stats`, `review templates list`, and `review verify`.
2. Add `--dry-run` options and request plans to commands that make external requests.
3. Add `--dry-run` preview to mutating local command `review export-feedback` to write nothing during dry run.
4. Remove echo-only previews and explicit `--dry-run` from `review rules test` without a shim.
5. Remove all 20 review command paths (and their `ai review` aliases) from `tests/fixtures/dry_run_gaps.json`.
6. Add unit tests and invariant coverage to verify dry-run behavior.

This change fits in one pull request.

## Capabilities

- `command-dry-run-class`: Extend capability with requirements for review request plans and review local execution without external requests.

## Impact

- All review commands obey the dry-run rule.
- External network, Valkey, and LLM requests are prevented in dry run.
- Operators can inspect planned requests before running reviews.

## Feasibility

We verified the command behaviors against `src/devops_cli/commands/review.py`.
Commands calling external endpoints via `httpx2`, `valkey`, or `git` are confirmed.
The dry run proxy and `PlannedRequest` mechanisms function cleanly in existing command groups.

## Existing Tool Considered

We considered Typer native dry-run support, but Typer does not generate request plans or handle external request suppression.
`devops_cli.dry_run.requests.PlannedRequest` is the established repository standard.
We delete legacy echo-only logic without adding dependencies.

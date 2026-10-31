# Proposal

## Why

The alternatives check lets the model decide whether to search for open tools. Over 14 days it searched about 4 times and returned not-applicable every time, including for a feature that integrates two products (#2946). A fixed rule must name the skip classes, and every other item must run at least one search before the check accepts any verdict.

## What Changes

- Add a SKIP_CLASSES constant list in the alternatives check module
- Add a classification function that returns the skip class name or None
- For skip-class items, return not-applicable with the class as reason, with no model call
- For non-skip items, reject a verdict reply that has no search recorded
- Give the model one additional turn to search after a rejected reply
- End as a failed check on a second reply without a search
- Add a table test covering each skip class with no model call
- Add a scripted-model test for the search-before-verdict rule
- Add a replay test that verifies the Firecrawl counter rises
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-alternatives`: skip-class-classification, search-before-verdict, firecrawl-counter-replay

## Impact

- Code: `src/devops_cli/roadmap/alternatives.py`
- Tests: `tests/test_roadmap_alternatives.py`

## Feasibility

- The premise is confirmed by docs/TELEMETRY.md:81, which defines devops_cli_firecrawl_searches_total as a counter for Firecrawl web searches, and k8s/README.md:609, which describes the Firecrawl search behavior and its metric.
- CONTEXT.md defines the Alternative term and the alternatives check verdicts: covers, partly, none, not-applicable.
- AGENTS.md rule 3 states to use an open tool before building, which is the principle this check enforces.
- The issue body cites devops_cli_roadmap_alternatives_total showing only not-applicable (about 34 checks) over 14 days, and devops_cli_firecrawl_searches_total showing about 4 searches in 7 days.
- The first check the implementation runs is uv run devops ci test tests/test_roadmap_alternatives.py to verify the table test and the search-before-verdict test.
- The second check is uv run devops ci to verify the full CI passes.

## Existing Tool Considered

No open, maintained tool or library covers the need to enforce a search-before-verdict rule inside the devops-cli alternatives check. The project builds this logic itself. The written cost is the tokens to build, keep and fix the constant list, the classification function, the search-enforcement guard, and the table and replay tests, plus the elapsed time to implement and debug them.

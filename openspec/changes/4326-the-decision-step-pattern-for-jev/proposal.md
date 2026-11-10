# Proposal: The decision-step pattern for Jev decision points

## Why

Closes #4326. Three trials used TypeSafe Jev (`typesafe/jev-1.14`) as a cheaper model, and all three failed their gates: the completeness check of a draft pull request (#4320), the labels of an intake proposal (#4323) and the screen before the verify step (#4282, a guessed threshold and no data). On 2026-11-10 the owner decided that Jev is no drop-in replacement for a model that writes text, and that the workflows must change to fit a decision model. The project has no record of how a Jev decision point is built, so each trial made its own choices.

## What Changes

- New ADR `docs/adr/0019-a-decision-step-asks-jev-short-closed-questions-about-evidence-that-tools-extract.md`. It decides seven rules of a decision step, ranks the candidate decision points by fit, lists what a decision model is not suited for, and names two pilots with their success bars.
- New capability spec `decision-steps` with the requirements: a closed question set, an evidence builder that tools run, thresholds fitted on labelled data, action bands, a shadow log and a fail-open rule.
- No code changes. Pilot 1 (the verify screen) is the work of #4282. Pilot 2 (the failure-class tail) is planned in the ADR and built later.

## Capabilities

- `decision-steps`: new capability.

## Impact

- No behavior change. The record binds the next decision steps: a step that does not follow it needs a new record.
- #4282, #4284 and any later Jev step cite the record.

## Feasibility

- The three trials and their numbers are in the issues and pull requests #4320, #4323 and #4282. The premise (a decision model works on short closed questions) is from `devops ai ask-jev` and from the TypeSafe cookbooks (`https://docs.typesafe.ai/cookbooks`): the SDE cascade, the line-by-line search and the parallel questions cookbook use many small questions about pieces that code extracts.
- The `DecisionRequest`, `NoulQuestion`, `ChoiceQuestion` and `ScoreQuestion` types are in `pydantic_ai/models/decision.py` of the locked version. A request has one state and many named questions, so a question about another piece needs another request.
- The success bar of pilot 1 is measured on the golden set of the stage job (`tests/fixtures/roadmap_eval/stage`, 56 cases, 317 labelled defects) with `devops roadmap eval verify`. The measure is in the pull request of #4282.

## Existing Tool Considered

TypeSafe Jev through the `DecisionModel` of pydantic_ai, as `src/devops_cli/ai/jev.py` wraps it. The record builds no second client and no new library. The cost of the record is one document and one spec in one pull request. The fits need labelled data, which the golden sets already hold. The change fits one pull request.

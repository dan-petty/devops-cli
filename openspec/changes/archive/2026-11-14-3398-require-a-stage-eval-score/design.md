# Design

## Context

`assess_merge_readiness` in `src/devops_cli/github/merge_readiness.py` reads the changed files and the body of a pull request. The readiness rules of the body and of the item run in `_judge_grounding`. The stage workflow requires the eval evidence, and no rule reads it.

## Goals

- Refuse a stage-change pull request that states no eval evidence.
- State the trigger path and the command in the blocker.

## Decisions

- **One pure function reads the body.** `stage_eval_problems` returns the problems of the evidence. The readiness check calls it once, with the first trigger path that the pull request changes. A pure function keeps the four refused forms and the passing forms offline.
- **Two accepted forms.** A replay states a number before and after and calls no model, as the workflow says. A live run states a score before and after and one `--model` name. A number must stand beside its word.
- **A new blocker kind.** `BlockerKind.STAGE_EVAL` keeps the rule apart from the body form and the item rules, so `pr monitor` and `pr ready` name it.

## Risks

- A body that states a score in prose without the words `before` and `after` is refused. The workflow requires the two words, and a person can edit the body.
- A body with a live run and two models is refused. The workflow says one model.

## Tests

- The four refused forms: no number, one number, two models, and `--model` with no name.
- A replay with two numbers passes.
- A live run with one model and two scores passes.
- A pull request with a trigger path and no evidence is not ready, and its blocker names the path.

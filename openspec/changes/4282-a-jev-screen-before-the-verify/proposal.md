# Proposal: A Jev screen before the verify step

## Why

Closes #4282. The model review of a plan (`stage_verify`) is the costliest model step before a draft opens. In the stage job it is an agent with read tools that runs for every plan, also for a plan with no defect. The golden set of the stage job (56 cases) is the data to measure a screen before it. This change is pilot 1 of the decision steps of ADR 0019: it builds the shared decision-step module and the verify screen on it, behind a setting that is off.

## What Changes

- New module `src/devops_cli/roadmap/decision_step.py`: the bands (`continue`, `review`, `flag`), the cuts as data (`Thresholds`), `band_of`, and `decide_all`, which sends one Jev request for each piece at the same time, with a model for each request, and raises on the first error so that a step fails open.
- New module `src/devops_cli/roadmap/decision_fit.py`: the fit of the cuts on labelled data (a cut for each question, or one shared cut), the score of fixed cuts on other cases, and the fixed split of the cases into two halves.
- New module `src/devops_cli/roadmap/stage/stage_jev_screen.py`: the screen. Code builds a short digest of the input of the review (the criteria of the issue, the groups of the plan, and the facts of tools about each group). One Jev request asks nine yes/no questions about it, one for each type of defect. The band follows the fitted cuts in `jev_screen_cuts.json`.
- New setting `roadmap.stage.jev_screen` with the values `off` (default), `shadow` and `on`. `shadow` asks Jev, logs and counts the band beside the result of the review, and always runs the review. `on` skips the review for the band `continue`. Any error, timeout or missing answer of Jev runs the review.
- Two counters: `devops_cli_roadmap_decision_step_total` (step, mode, band) and `devops_cli_roadmap_decision_step_review_total` (step, band, reviewer). The pilot adds 8 and 6 series.
- New command `devops roadmap eval screen`. It asks Jev about each case, reads stored runs of the reviewer alone, fits the cuts on one fixed half (`tests/fixtures/roadmap_eval/stage/split.json`), scores them on the other half and repeats with the halves swapped. It reports the skipped reviews, the lost serious defects, the false clears, the oracle and the cost. `--dry-run` makes no request, `--from` fits again from an earlier report with no request, and `--write-cuts` writes the data file.

## Capabilities

- `roadmap-stage`: ADDED requirements for the screen and its setting.
- `roadmap-stage-eval`: ADDED requirement for the screen score.

## Impact

- No behavior change while the setting is `off`.
- With `shadow`, one Jev request for each review, about 1,700 input tokens (0.00007 USD), and the review runs as before.
- A new key `roadmap.stage.jev_screen` in the ConfigMap `devops-cli-config`. The model `RoadmapStageConfig` ignores unknown keys, so the key is safe before or after the image. This change applies nothing.

## Feasibility

- Jev answers a request with many Noul questions about one state (`pydantic_ai/models/decision.py` of the locked version; `devops ai ask-jev`). The gateway serves `POST /v1/systemone` for `typesafe/jev-1.14` (live calls on 2026-11-10 answered all 56 requests of the golden set with no error).
- The reviewer alone was run on the golden set with the model `deepseek-v4.1-flash-1017`: 48 of the 56 cases have a commit that the agent can read (`cases_with_commit`); the other 8 are synthetic gate probes with one defect each. The reviewer found 104 of the 177 labelled serious defects of those 48 cases.
- **The bar cannot be met on this set.** The bar of ADR 0019 asks for no lost serious defect and at least 30% of the reviews skipped. The reviewer alone found no serious defect in 9 of the 48 cases (19%), and 5 of these are the good plans. No screen can skip more than those 9 with no loss, even one that knows the answer. The numbers of the designs that were tried are in the comment of the pull request. On the recorded split, the best design (one shared cut) lost no serious defect in both directions and skipped 4% of the reviews on the other half. A cut for each question skipped 26% and 12% but lost 6 serious defects in one direction.
- The thresholds in `jev_screen_cuts.json` come from `devops roadmap eval screen --write-cuts` on the 48 reviewed cases. The setting stays `off`.

## Existing Tool Considered

TypeSafe Jev through `pydantic_ai`'s `DecisionModel`, as `src/devops_cli/ai/jev.py` wraps it. The module reuses `create_jev_model`, and sends the request through one function (`_decide_one`) so that `decide_with_jev` of #4319 replaces its body. The scorer of the golden set (`matched_defects`) is reused. No second client and no new library. The cost of the new code is three modules, one setting, two counters and one command, and no code is deleted.

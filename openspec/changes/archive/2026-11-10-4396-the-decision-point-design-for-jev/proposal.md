# Proposal: The decision-point design for Jev workflows

## Why

Closes #4396. The owner asked on 2026-11-10 whether the Service uses Jev as a decision model is built to be used, or in workflows built for a generation model. The client is right: it uses the pydantic_ai `DecisionModel` and typed questions. The workflows are not. Every pilot is a gate or a judge on a step that a generation model still runs. Each pilot has its own setting, metric and log. The cookbook functions in `src/devops_cli/ai/jev.py` have no caller. The owner decided to build decision-model workflows when a decision model is configured and enabled.

The pilots also show that a decision model is not better by nature. It works on short closed questions about evidence that tools extract, with cuts fitted on labelled data. It failed on a long diff and on a structured generation answer, and a rule beat it on two small decisions. So the design puts the rule first, the model second and the current behavior last, and it measures the benefit of each point.

## What Changes

- New ADR 0020. It defines the decision point as a unit, the resolver chain, the settings `ai.decision_model` and `roadmap.decisions`, the shadow record and the outcome join, the one metric `devops_cli_decision_point_total` (at most 60 series for the catalogue), the catalogue of points with their question set, evidence, baseline rule, label source and success bar, what stays generation, and the order of the migration.
- ADR 0019 is amended in three places: its table of ranked points and its section of pilots point to the catalogue of ADR 0020, and its pilot 2 text gives the measured result.
- New capability `decision-workflows` with the requirements of the unit.
- Two requirements of `decision-steps` are modified: the shadow requirement names the mode setting and the one metric, and the fail-open requirement adds the case of no configured model.
- No code. The registry and the first migration are the next item. `stage.explore_stop` in shadow is the item after it.

## Capabilities

- `decision-workflows`: new.
- `decision-steps`: MODIFIED requirements "A decision step runs in shadow before a switch" and "A decision step fails open".

## Impact

- No behavior change in this pull request.
- The next items remove the settings `roadmap.stage.jev_screen`, `roadmap.intake.jev` and `roadmap.stage.jev_completeness` and the two counters of the screen. Each of them states the change of the live ConfigMap and its order.
- This pull request applies nothing to the cluster.

## Feasibility

- The premise is that the existing parts can carry the design. `src/devops_cli/roadmap/decision_step.py` holds the bands, `Cut`, `Thresholds` and `decide_all`. `decision_fit.py` holds the fit and the halves. `src/devops_cli/ai/jev.py` holds `decide_with_jev` and `create_jev_model`. The registry reuses all of them.
- The settings premise was read in `src/devops_cli/config/settings.py`: `AIConfig` has `extra="forbid"`, and `RoadmapConfig`, `RoadmapStageConfig` and `RoadmapIntakeConfig` have `extra="ignore"`. So `ai.decision_model` needs the image first and `roadmap.decisions` is safe at any time. `RoadmapImplementConfig.ladder` is the pattern of a mapping with validated keys.
- The evidence of the pilots is in the ledgers of 2026-11-10: the screen (56 requests of the golden set, 48 reviewer runs), the completeness check and the intake labels (ADR 0019), the failure tail (271 stop comments of 4 repositories, 8 untyped stops) and the budget extension (33 labelled checkpoints from 28 items, 16 right to extend; 419 runs in 14 days).
- The traces of the stage planner that are stored today (two runs of #3387) hold the token and call count at each request and no tool, path or order. The design for `stage.explore_stop` therefore says that the shadow record is the data of the fit.

## Existing Tool Considered

TypeSafe Jev through pydantic_ai `DecisionModel`, as in ADR 0019. No other open tool covers a resolver chain with a rule first and a typed decision model second. This change adds a record and a spec and deletes no code.

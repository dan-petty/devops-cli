# Design

## Decisions

The decisions are in ADR 0020 (`docs/adr/0020-a-decision-point-is-a-unit-of-a-workflow-with-a-resolver-chain-and-a-rule-goes-before-a-decision-model.md`). In short:

- **The unit is the decision point.** A name, a closed question set, an evidence builder that tools run, cuts that are data, three action bands, a mode, and an outcome join.
- **The resolver chain** is a rule, then the decision model, then the current behavior. A rule that meets the bar of its point excludes the model.
- **Two settings.** `ai.decision_model` holds the model name (empty means none). `roadmap.decisions` maps a point name to `off`, `shadow` or `on`, and validates its keys against the registry as the ladder validates its step classes. The registry refuses `on` for a point with no fitted cuts.
- **One counter and one record.** `devops_cli_decision_point_total` has the labels point, resolver, band and mode. It has at most 60 series for the six points of the catalogue. The record of a decision is one log line, and the outcome is a second line with the same identifier. A pure function joins them into the labelled cases of the next fit.
- **The catalogue** gives for each point the questions, evidence, baseline rule, label source and bar before the point is built.
- **The order of the migration** has seven steps, each its own pull request.

## Rejected alternatives

- **Leave each pilot as it is.** Each pilot has its own setting, metric and log, none joins its decision to the outcome, and none puts a rule ahead of the model. The measured pilots show that the rule is the better first resolver.
- **A model first and a rule as a check.** A rule with no error on the labelled data (the failure tail and the budget extension) costs no request and adds no failure mode.
- **A setting and a metric for each pilot.** A mapping adds a point with no new setting, and one counter with a bounded `point` label stays at 60 series.
- **A model on for all points when it is configured.** The model name says only that a model exists. The benefit is measured for each point.
- **Name the tier route `implement.tier_route`.** Issue #4284 puts the choice before the first plan call of the stage planner, so the point is `stage.tier_route`.

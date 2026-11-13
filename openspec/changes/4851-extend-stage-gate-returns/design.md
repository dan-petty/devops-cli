# Design

## Decisions

- **The rule reads findings, not counts only.** The rule needs the gates of the findings that stop a reply, for the failure text. So `gate_extension` takes the findings of the reply before and of the last reply, and compares them by `StageFinding.key` (the gate and the text with the digits masked), as `return_counts` does.
- **No finding stays, and no `never` finding.** The issue gives the rule "no stuck and no never finding and (every problem of the reply before is gone, or fewer problems, or less problem text)". With no finding that stays, every finding of the reply before is gone, so the last clause is always true, and the rule needs no other count. #5136 at return 3 (`stuck=0`, one `stage_problem_trace_path` finding) passes it. The record of #4472 (the same stale test path again) fails it as `stuck`.
- **The guard comes first.** An item that used its extra return gets no other (`used`). With `roadmap.stage.gate_returns` 0, no return compares two replies, and the reply gets no extra return (`first`). A code that `stage_finding_classes.json` does not hold, such as `uncoded`, is no `never` code: the job returns such a reply today.
- **One extra return for each item.** The issue gives "at most 1 extension". A count for each item, and not for each reply, bounds an item with repair rounds of the review to one more plan run: 5R + 7 = 22 plan runs at most.
- **The extra return keeps the drain guard.** The decision comes first and the drain guard of #4900 runs after it, as before each return. So a stuck reply in a drain still fails the item with `plan_defect`, and an extended reply in a drain ends the round with the stop. The end line then gives `result=ended`.
- **An end line for each extra return.** `_returned` holds a flag from the grant of the extra return until the checks judge its reply. A `finally` block logs `ended` when the run ends before that: a stop of the Service, a provider error, a broken schema or a reply of placeholders. The error itself still goes up.
- **Two counters.** `devops_cli_roadmap_stage_gate_extension_total{result}` counts the decisions (5 series), and `devops_cli_roadmap_stage_gate_extension_ends_total{result}` counts the ends (3 series). The labels are fixed enumerations (`GateExtension`, `ExtensionEnd`), and no label holds a repository or an item. The log lines hold the repository and the item.
- **A constant, not a setting.** The count of extra returns is a guard of the cost of an item, as `CONST_ROADMAP_STAGE_VERIFY_REPAIR_ROUNDS_CEILING` is. A live switch for each point comes with the modes of #4847.

## Rejected alternatives

- **A decision point `stage.gate_returns` in `decision_registry` now.** `ResolverChain` stops at the rule when the rule gives a band, so the model never adds a yes; a point needs a mode in `roadmap.decisions` to run at all, and `on` needs a cuts file that no fit made (#4847, #5272). The follow-up #5386 registers the point when the chain supports it.
- **Ask Jev with `decide_with_jev` at the cap, outside the framework.** It is a second decision framework, which #4847 refuses, and its answer has no fitted cut to act on (ADR 0019 rule 4).
- **Extend while the count of findings drops, as the review rounds do (#5066).** #5136 at return 3 had 1 finding before and 1 after, so a count rule refuses it, and the plan improved: the finding of the reply before was gone.
- **Raise `CONST_ROADMAP_STAGE_GATE_RETURNS_CEILING` to 4.** A fourth return then also goes to a reply whose finding stays, which #4472 shows that no return fixes.
- **Refuse at once on a `never` finding.** The seed class of `stage_problem_missing_test_file` comes from the replies of the gate defect #4791, which is fixed, so the refusal would refuse plans that the fixed gate passes.
- **A time guard of 2700 s for each item (#4843).** The stage row has no wall-clock deadline for the guard to nest in (#4802), so the guard would be a new cap. The count bounds the cost.

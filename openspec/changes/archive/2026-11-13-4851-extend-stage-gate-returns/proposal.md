# Proposal: #4851

## Why

A reply that the stage checks refuse goes back to the planner `roadmap.stage.gate_returns` times (3 by default and at most), and a reply that the checks refuse after the last return fails the item with the class `plan_defect`. The cap stops a plan that still improves. On 2026-11-13, item #5136 stopped at its third return while its gate findings went from 3 to 1, and the last return removed that finding and found 1 new one (`stage_problem_trace_path`). The stage job staged 1 of 3 attempts in the 6 hours before. The owner direction of 2026-11-11 makes a cap a soft cap: at the cap, short deterministic progress facts decide one bounded extension, up to a hard ceiling and a maximum count of extensions, and each decision is logged and counted. Closes #4851.

## What Changes

- The change fits one pull request.
- At the last gate return, the rule `gate_extension` (`src/devops_cli/roadmap/stage/stage_findings.py`) decides whether a refused reply gets one more return. The guard comes first: an item gets at most `CONST_ROADMAP_STAGE_GATE_RETURN_EXTENSIONS` (1) extra return. Then the rule reads the findings of the last two refused replies (#4846): no finding of the reply before stays, and no finding of the last reply has the fix class `never` in `stage_finding_classes.json`. The rule makes no model call.
- One reply gets at most `roadmap.stage.gate_returns` + 2 planner requests, and an item 5R + 7 = 22 plan runs at most, against 21 before. The drain guard of #4900 still runs before the extra return, as before each return.
- Each decision logs `stage gate extension: repo=<owner/repo> item=#<n> returns=<n> in=<n> gone=<n> stuck=<n> new=<n> never=<n> result=<result> version=<version>` and adds 1 to the new counter `devops_cli_roadmap_stage_gate_extension_total{result}` (`extended`, `used`, `first`, `stuck` or `never`, 5 series).
- Each extra return logs `stage gate extension end: repo=<owner/repo> item=#<n> returns=<n> result=<passed|refused|ended> version=<version>` and adds 1 to the new counter `devops_cli_roadmap_stage_gate_extension_ends_total{result}` (3 series). These lines are the labelled outcomes for a later fit of a decision model.
- The failure text of a reply that stays refused names its return and the stop, for example `The change still fails its checks after return 3 (no extra return: a finding of the gate paths stays from the reply before): ...`.
- The description of `roadmap.stage.gate_returns`, `docs/roadmap/stage.md`, `docs/CLUSTER.md` and the generated `docs/ENV_VARS.md` and `docs/TELEMETRY.md` state the rule, the lines and the counters.
- The description of `devops_cli_roadmap_stage_gate_problems` counts the reply of the extra return: at most `roadmap.stage.gate_returns` + 2 replies, so 5 series for each repository.
- The stage job behavior changes, so the change has a spec delta in `roadmap-stage/returns`. The requirements of `roadmap-stage/spec-delta`, `roadmap-stage/plan-text` and `roadmap-stage/verification` that bound a return to `roadmap.stage.gate_returns` also name the extra return.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage/returns`: A refused reply that makes progress gets one extra return.
- `roadmap-stage/spec-delta`: A failed validation also gets the extra return.
- `roadmap-stage/plan-text`: A title problem also gets the extra return.
- `roadmap-stage/verification`: A refused revision of a repair round also gets the extra return.

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/round_log.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_eval_render.py` (the dry run of `devops roadmap eval stage` counts the extra plan run), `src/devops_cli/roadmap/stage/stage_findings.py`, `src/devops_cli/telemetry/instruments.py`.
- Tests: `tests/roadmap/stage/test_roadmap_stage_gate_extension.py` (new), `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/stage/test_roadmap_stage_plan_defect_limit.py`, `tests/roadmap/test_roadmap_limit_classes.py`.
- Documents: `docs/roadmap/stage.md`, `docs/CLUSTER.md`, `docs/ENV_VARS.md` and `docs/TELEMETRY.md` (generated).
- Cost: an extended item makes one more plan run (about 728 s at p90 on 2026-11-11). No setting, no ConfigMap key and no manifest changes. The Service gets the rule with the next release image.

## Feasibility

- Source on `main` at 4ef7c6f11 (0.127.0): `StageJob._returned` in `src/devops_cli/roadmap/stage/stage.py` raises the `plan_defect` failure when `returns >= self._gate_returns`. `roadmap.stage.gate_returns` has the default 3 and `le=CONST_ROADMAP_STAGE_GATE_RETURNS_CEILING` (3), so the issue's "hard ceiling 3 returns (4 planner asks)" is already the default. The extra return goes past the setting, so one reply gets at most 5 planner requests.
- `return_counts`, `StageFinding.key` and `load_finding_classes` (#4846) exist, and `stage_finding_classes.json` holds the class `never` for `stage_problem_missing_test_file` only (0 of 17 fixed). `stage_problem_trace_path` is `model_fixable` (13 of 16).
- Loki, `{namespace="devops"} |= "item=#5136"`, 2026-11-13 06:00Z to 06:50Z: `stage gate findings:` return 1 `in=3 gone=2 stuck=1 new=0`, return 2 `in=1 gone=0 stuck=1 new=0`, return 3 `in=1 gone=1 stuck=0 new=1`, then `stage gate returns: ... returns=3 result=refused gates=trace:1 codes=stage_problem_trace_path:1` and `stage item failed: ... class=plan_defect`. The returns ran in a repair round of the model review (review round 0 had 3 open findings). The test fixture holds these counts.
- The decision model part is blocked. #4847 (the soft-cap chain of decision points, Status New) is not built: `ResolverChain` runs the rule before the model and has no mode in which the model adds an extension, and `decision_registry.REGISTRY` holds only `stage.verify_screen`. #5272 (Status Ready, not built): `ResolverChain.decide` calls `asyncio.run`, and a point in `shadow` loads with no cuts file. No labelled outcome of this decision exists, so no cut can be fitted (ADR 0019 rule 4; `check_modes` refuses `on` with no cuts file). So the rule decides, which is the fail-safe path of the owner direction, and the follow-up #5386 adds the model. The evidence on #4847 (2026-11-12) also recommends that only the rule acts before a fit.
- Parts 1 and 2 of the issue (refuse at once on a `never` or stuck finding, the class `check_suspect`, and a return to New after 5 item-class failures) are not built. #4791, the known gate defect that `check_suspect` names, is closed. The `never` seed of `stage_problem_missing_test_file` comes from the replies that #4791 refused in error, so a refusal at once on it would refuse replies that the fixed gate passes. A refusal at once also removes returns, and the owner direction loosens caps until each job reaches 80%. The follow-up #5386 holds this part, to build after the classes are fitted again on replies after #4791.
- The time guard of the tracker #4843 (2700 s for each item) has no outer limit to nest in: the stage row has no wall-clock deadline (#4802). The extension is bounded by its count (one plan run for each item), and each plan run keeps its own tool call and request limits.

## Existing Tool Considered

No open tool decides the returns of a plan. The change reuses the finding codes, the return counts and the fix classes of #4846, the drain guard of #4900, the log module of #4535 and the project instruments, as #5066 did for the review rounds. It costs about 400,000 tokens to build and test, about 2,000 tokens to keep, and about 3 hours elapsed. It adds no dependency.

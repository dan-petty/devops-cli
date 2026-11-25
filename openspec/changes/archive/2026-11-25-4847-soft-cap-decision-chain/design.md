# Design

## Decisions
- **Reuse `DECISION_POINT_TOTAL` instead of adding separate cap counters**: `implement.extension` emits on `devops_cli_decision_point_total` (raising `CONST_ROADMAP_DECISION_POINT_MAX_SERIES` from `92` to `110`: `+18` for `implement.extension` across `shadow` `[7]`, `on` `[7]`, and `rule` `[4]`) while `DecisionRecord` records `rule_band`, `model_band`, and `guard` alongside existing `ROADMAP_IMPLEMENT_EXTENSION_TOTAL`.
- **Add `Mode.RULE` without requiring a cuts file on disk**: `check_modes` lets `off` and `rule` load without `implement_extension_cuts.json` so `implement.extension` can run safely with guards and rule first while collecting model `answers` (`model_band=None`) before cuts exist. Existing `shadow` and `on` still require a cuts file (`#5272`).
- **Enforce fit bar for fit-bar-gated points without breaking legacy points**: `fit_bar_problems_from_data` / `Thresholds.fit_bar_problems` checks `>= 30` cases, `>= 10` per label, and a passing halves check. `FIT_BAR_POINTS` (`{"implement.extension"}`) and `DecisionPoint.requires_fit_bar` enforce that bar on `Mode.ON` without default constant cuts while leaving existing `stage.verify_screen` and `alternatives.reply_fixable` behavior intact.
- **Evaluate guards as an ordered pipeline before `rule` and `model`**: `DecisionPoint.guards` runs `(service_draining, hard_ceiling, outer_limits, loop_guard)` in declaration order; the first failing guard returns `Resolver.FALLBACK`, `band=None`, `guard="<name>"`, and skips both rule and model calls.
- **Keep `fix-checks` deferred and amend ADR 0020 via `Status History`**: The `fix-checks` decision chain stays deferred to its own issue per `#4847`, and `docs/adr/0020-*.md` gains only a `Status History` line so its frozen `body-hash` remains valid.

## Rejected alternatives
- **Adding four bespoke soft-cap Prometheus counters (`_cap_decisions_total`, etc.)**: Rejected per ADR 0020 and the `#4847` refine resolution; extra counters multiply cardinality and duplicate `DECISION_POINT_TOTAL` and `DecisionRecord`.
- **Allowing a default constant cut before 30+ outcomes exist**: Rejected; switching `"on"` without empirically fitted cuts meeting the fit bar risks silent over-extension before data exists.
- **Implementing the `fix-checks` chain in this change**: Explicitly deferred in `#4847` to keep this change focused on the shared decision chain and its first soft-cap point (`implement.extension`).

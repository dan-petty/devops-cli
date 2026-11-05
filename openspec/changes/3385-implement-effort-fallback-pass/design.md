# Design

## Decisions

- **Run one pass for each effort value, in the order of the setting.** `plan_implement` walks each pass with `walk_named`. The first pass that takes an item supplies the run, up to the limit. A later pass takes no item in that run. `walk_named` orders by priority, so a single walk over both efforts would take a higher-priority medium item before a lower-priority low item (`src/devops_cli/roadmap/stage.py`, `_open_items`). The passes keep the low-effort preference of the issue.
- **Let a pass after the one in use judge only the probe.** `walk_named` with a limit of 0 and a `probe` judges only the probe item. `devops roadmap explain` therefore gets a reason for a medium item that waits behind a low item, and the Service round, which passes no probe, reads no extra item.
- **Keep the set in one setting, `roadmap.implement.effort`, typed as a list.** The list type matches `roadmap.stage.filter`, which the ConfigMap and the environment already read as a list. The issue writes the default as `low,medium`, which is the environment form. A comma string would need its own parser, and the list needs none.
- **Validate each value against `CONST_ROADMAP_SIZE_OPTIONS`.** The table holds `High`, `Medium` and `Low`. The validator compares the lower-case form, so the set uses the labels `effort/low`, `effort/medium` and `effort/high`. A repeated value is refused, so a pass never runs twice.
- **An explicit `--filter effort=` makes one pass with the filter as given.** `parse_filters` already uses the options and drops the defaults when options are given. The set therefore applies only when the filter names no effort.
- **Give the plan the pass in use and a fallback flag.** `ImplementPlan.effort` holds the effort of the pass that took the run, and `ImplementPlan.fallback` is true when that pass is not the first value of the set. `render_implement_plan` reads both, so the run report names the pass with no second selection.
- **Name the set in explain from the plan.** `explain` already plans the item. It states the set and whether the fallback applies to the item: the fallback applies when the item's effort is the pass in use and that pass is the fallback.
- **Reject a high-effort item through the union filter.** The union of the set is a `StageFilter` with the family `effort` and the labels of every value. Its `mismatch` gives the existing reason `The filter takes effort low or medium. The item has effort high.`, so no new reason text is needed for a high-effort item.

## Rejected alternatives

- **One walk over `effort=low` and `effort=medium`.** Walk order is priority first (`priority_order` in `stage.py`). A higher-priority medium item would take the run before a lower-priority low item, so acceptance criterion 1 fails.
- **Two settings, one for the first pass and one for the fallback.** Two keys allow a contradictory pair, and the order of the keys then needs a rule. One ordered list has no such problem.
- **A code constant with no setting.** The issue asks for a setting, and a person could not change the set without a release.
- **A fallback when the filter names no low-effort item.** One low-effort item that the job leaves out, for example a claimed item, would then block every medium item. The fallback applies when the low pass takes no item.
- **Filling the limit from the next pass.** A run that mixes efforts weakens the low-effort preference, and its report would name two passes.
- **Storing the pass on the job record of the issue.** The record holds the stops and branches of an item. The pass belongs to one run, so it goes on the plan.

## Shape of the change

- `DEFAULT_IMPLEMENT_FILTERS` names `status=ready` and `status=planned`. The effort passes come from the setting.
- `ImplementPlan` gains `effort` and `fallback`. `render_implement_plan` prints the pass and the fallback note.
- `Explanation` in `explain.py` gains the effort line for the implement job.
- `messages.py` gains the texts for the pass, the fallback, the later pass and the explain line.
- `k8s/devops/configmap.example.yaml` holds `roadmap.implement.effort` with the default list. The manifest group has no test. A command that reads the example proves it.

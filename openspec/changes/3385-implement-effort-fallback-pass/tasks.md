# Tasks

## 1. Add the setting that holds the effort set

Reads: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/errors.py`, `tests/roadmap/test_roadmap_stage_settings.py`. Changes: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/lang/en/errors.py`, `tests/roadmap/test_roadmap_stage_settings.py`.

- [x] 1.1 Add to `tests/roadmap/test_roadmap_stage_settings.py` a test that the setting `roadmap.implement.effort` defaults to `low` and then `medium`, and a parametrized test that a config file holding an unknown value `huge`, or a value held twice, is refused with a validation error that names the value
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_settings.py` fails on the base
- [x] 1.2 Declare `DEFAULT_ROADMAP_IMPLEMENT_EFFORT` in `src/devops_cli/config/defaults.py` as `("low", "medium")`, add the field `effort` to `RoadmapImplementConfig` in `src/devops_cli/config/settings.py` with a validator that refuses a value that is no effort value of `CONST_ROADMAP_SIZE_OPTIONS` and a repeated value, and add the refusal text to `src/devops_cli/lang/en/errors.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_settings.py` passes

## 2. Select the items of each effort pass in order

Reads: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/stage_filter.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/test_roadmap_implement_selection.py`. Changes: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/explain.py`, `tests/roadmap/test_roadmap_implement_selection.py`.

- [x] 2.1 Change `tests/roadmap/test_roadmap_implement_selection.py` so the default filter test asserts `("status=ready", "status=planned")`, and add tests that a Ready medium-effort item is taken when no low-effort item is selectable, that a claimed low-effort item lets a medium-effort item run, that a high-effort item is not taken, that a low-effort item of a lower priority is taken before a medium-effort item of a higher priority, that an explicit `effort=high` filter replaces the set, and that the set `low` alone takes no medium-effort item
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_selection.py` fails on the base
- [x] 2.2 Remove the `effort=low` entry of `DEFAULT_IMPLEMENT_FILTERS` in `src/devops_cli/roadmap/implement.py`, add the function that builds one filter for each effort value of the set and the union filter of the set, add `effort` and `fallback` to `ImplementPlan`, and walk the passes in order in `plan_implement` so that each later pass judges only the probe, with the probe of a later pass left out with the reason that the run takes an earlier effort first
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_selection.py` passes
- [x] 2.3 Use the union filter of the set for the matching of `_implement_verdict` in `src/devops_cli/roadmap/explain.py` and for the listing of `--why`, so a high-effort item gets the reason of the filter
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_explain.py tests/roadmap/test_roadmap_implement_selection.py` passes

## 3. Name the effort pass in the run report and in explain

Reads: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_explain.py`, `tests/roadmap/test_roadmap_implement_selection.py`. Changes: `src/devops_cli/roadmap/implement.py`, `src/devops_cli/roadmap/explain.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_explain.py`, `tests/roadmap/test_roadmap_implement_selection.py`.

- [x] 3.1 Add to `tests/roadmap/test_roadmap_implement_selection.py` a test that the rendered plan of a run that takes a medium-effort item names the effort pass `medium` and the fallback, and add to `tests/roadmap/test_roadmap_explain.py` a test that `explain` on a Ready medium-effort item names the set `low,medium` and says that the fallback pass applies, and a test that it names the low-effort item that the run takes first when such an item is selectable
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_selection.py tests/roadmap/test_roadmap_explain.py` fails on the base
- [x] 3.2 Add to `src/devops_cli/lang/en/messages.py` the texts of the effort pass, the fallback note, the later pass reason and the explain line, render the pass in `render_implement_plan`, and render the effort line of the implement job in `render_explanation` from the plan of `_implement_verdict`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_explain.py tests/roadmap/test_roadmap_implement_selection.py` passes

## 4. Hold the setting in the example ConfigMap

Reads: `k8s/devops/configmap.example.yaml`, `tests/config/test_k8s_devops_runtime.py`. Changes: `k8s/devops/configmap.example.yaml`.

- [ ] 4.1 Add under `roadmap.implement` in `k8s/devops/configmap.example.yaml` the list `effort` with the entries `low` and `medium`, and a comment that names the fallback pass
  - Verification: `uv run devops ci test tests/config/test_k8s_devops_runtime.py` passes

## 5. Document the effort set

Reads: `docs/roadmap/implement.md`, `src/devops_cli/config/settings.py`. Changes: `docs/roadmap/implement.md`, the generated documents of `devops docs generate --sync-readme`.

- [ ] 5.1 Replace the default filter of `docs/roadmap/implement.md` with `status=ready` and `status=planned`, and describe the effort passes, the fallback, the explicit `--filter effort=` and the setting `roadmap.implement.effort`
  - Verification: `uv run devops ci docs` passes
- [ ] 5.2 Run `uv run devops docs generate --sync-readme` so that the generated documents name the setting `roadmap.implement.effort`
  - Verification: `uv run devops docs generate --sync-readme && uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: confirm the reversal of the archived decision in `openspec/changes/archive/2026-10-31-2906-wide-stage-and-implement-filters/proposal.md` that kept medium items Staged for a person.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
